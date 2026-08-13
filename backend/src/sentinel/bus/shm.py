"""Paylaşımlı bellek kare havuzu.

Neden var
---------
1080p ham kare ~6 MB, 720p ~2.6 MB. Saniyede 80 kare üretiliyorsa bu
~210 MB/sn eder. Bunu Valkey'den geçirmek serileştirme + ağ kopyalaması
demektir; hiçbir mesaj kuyruğu bu iş için tasarlanmamıştır.

Çözüm: kareler **paylaşımlı bellekte** durur, Valkey'den yalnızca
"şu slotta, şu boyutta bir kare var" referansı geçer (~200 bayt).
Süreçler arası kopyalama sıfırdır — aynı fiziksel belleğe bakarlar.
(PLAN.md §4.2)

Slot yönetimi
-------------
Boş slot listesi **Valkey'de** tutulur (`shm.free` listesi). Sebebi:
slot havuzunu üreten ve tüketen ayrı süreçlerdir; paylaşımlı bellekte
kilitsiz bir serbest liste yazmak yerine, zaten elimizde olan atomik
veri yapısını kullanmak hem daha basit hem daha sağlam.

Bu tasarımın bedava getirdiği şey **geri basınç**: tüketici yavaşlarsa
boş slot kalmaz, üretici slot bulamaz ve kareyi *atar*. Sınırsız kuyruk
yerine kontrollü kare kaybı — gerçek zamanlı sistemde doğru davranış
(PLAN.md §4.3).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from multiprocessing import shared_memory
from types import TracebackType

import numpy as np

# 1280×720×3 (BGR) = 2 764 800 bayt. Tüm kameralar bu boyuta sığar;
# gerçek şekil mesajda taşınır.
DEFAULT_SLOT_BYTES = 1280 * 720 * 3
DEFAULT_SLOT_COUNT = 128
DEFAULT_POOL_NAME = "sentinel_frames"

FREE_LIST_KEY = "shm.free"


@dataclass(frozen=True, slots=True)
class FrameRef:
    """Bir karenin paylaşımlı bellekteki adresi. Mesajda bu taşınır."""

    slot: int
    height: int
    width: int
    channels: int
    dtype: str = "uint8"

    @property
    def nbytes(self) -> int:
        return self.height * self.width * self.channels

    def to_dict(self) -> dict[str, str]:
        """Valkey Stream alanları düz string olmak zorunda."""
        return {
            "slot": str(self.slot),
            "h": str(self.height),
            "w": str(self.width),
            "c": str(self.channels),
            "dtype": self.dtype,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> FrameRef:
        return cls(
            slot=int(data["slot"]),
            height=int(data["h"]),
            width=int(data["w"]),
            channels=int(data["c"]),
            dtype=data.get("dtype", "uint8"),
        )


class FramePoolError(RuntimeError):
    """Havuz oluşturma/bağlanma hatası."""


class FramePool:
    """Sabit boyutlu slotlardan oluşan paylaşımlı bellek bloğu.

    Sahibi (`create=True`) bloğu oluşturur ve kapanışta siler.
    Diğer süreçler `create=False` ile aynı bloğa bağlanır.
    """

    __slots__ = ("_buffer", "_owner", "_shm", "_slot_bytes", "_slot_count")

    def __init__(
        self,
        *,
        name: str = DEFAULT_POOL_NAME,
        slot_count: int = DEFAULT_SLOT_COUNT,
        slot_bytes: int = DEFAULT_SLOT_BYTES,
        create: bool = False,
    ) -> None:
        self._slot_count = slot_count
        self._slot_bytes = slot_bytes
        self._owner = create
        total = slot_count * slot_bytes

        try:
            if create:
                # Aynı isimde artık bir blok kalmışsa (çökme sonrası) temizle
                with contextlib.suppress(FileNotFoundError):
                    stale = shared_memory.SharedMemory(name=name)
                    stale.close()
                    stale.unlink()
                self._shm = shared_memory.SharedMemory(name=name, create=True, size=total)
            else:
                self._shm = shared_memory.SharedMemory(name=name)
                if self._shm.size < total:
                    raise FramePoolError(
                        f"Havuz beklenenden küçük: {self._shm.size} < {total}. "
                        "Farklı ayarlarla oluşturulmuş olabilir."
                    )
        except FileNotFoundError as exc:
            raise FramePoolError(
                f"'{name}' havuzu yok. Önce ingest worker'ı başlatın."
            ) from exc

        self._buffer = np.ndarray((total,), dtype=np.uint8, buffer=self._shm.buf)

    # ─── Bağlam yöneticisi ───────────────────────────────────

    def __enter__(self) -> FramePool:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Bloğu kapatır; sahibiyse işletim sisteminden de siler."""
        # numpy görünümü, buffer serbest bırakılmadan önce düşmeli
        self._buffer = np.ndarray((0,), dtype=np.uint8)
        self._shm.close()
        if self._owner:
            with contextlib.suppress(FileNotFoundError):
                self._shm.unlink()

    # ─── Kare yazma / okuma ──────────────────────────────────

    def write(self, slot: int, image: np.ndarray) -> FrameRef:
        """Kareyi slota kopyalar ve referansını döndürür.

        Tek kopyalama burada olur (numpy → paylaşımlı bellek).
        Bundan sonra kare hiç kopyalanmaz.
        """
        self._check_slot(slot)
        if image.dtype != np.uint8:
            raise ValueError(f"Yalnızca uint8 destekleniyor, gelen: {image.dtype}")
        if image.nbytes > self._slot_bytes:
            raise ValueError(
                f"Kare slota sığmıyor: {image.nbytes} > {self._slot_bytes} bayt "
                f"(şekil {image.shape})"
            )

        start = slot * self._slot_bytes
        flat = np.ascontiguousarray(image).reshape(-1)
        self._buffer[start : start + flat.size] = flat

        height, width = image.shape[:2]
        channels = image.shape[2] if image.ndim == 3 else 1
        return FrameRef(slot=slot, height=height, width=width, channels=channels)

    def read(self, ref: FrameRef, *, copy: bool = False) -> np.ndarray:
        """Slottaki kareyi ndarray olarak verir.

        Varsayılan olarak **kopyalamaz** — dönen dizi paylaşımlı belleğe
        bakar. Slot serbest bırakıldıktan sonra bu diziye dokunmak
        tanımsız davranıştır. Veriyi saklayacaksan `copy=True` kullan.
        """
        self._check_slot(ref.slot)
        start = ref.slot * self._slot_bytes
        view = self._buffer[start : start + ref.nbytes].reshape(
            ref.height, ref.width, ref.channels
        )
        return view.copy() if copy else view

    def _check_slot(self, slot: int) -> None:
        if not 0 <= slot < self._slot_count:
            raise IndexError(f"Geçersiz slot {slot} (0..{self._slot_count - 1})")

    # ─── Özellikler ──────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._shm.name

    @property
    def slot_count(self) -> int:
        return self._slot_count

    @property
    def slot_bytes(self) -> int:
        return self._slot_bytes

    @property
    def total_bytes(self) -> int:
        return self._slot_count * self._slot_bytes


__all__ = [
    "DEFAULT_POOL_NAME",
    "DEFAULT_SLOT_BYTES",
    "DEFAULT_SLOT_COUNT",
    "FREE_LIST_KEY",
    "FramePool",
    "FramePoolError",
    "FrameRef",
]
