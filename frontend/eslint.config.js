// ESLint yapılandırması — ön yüzün kalite kapısı.
//
// ⚠⚠ NEDEN ŞİMDİ EKLENDİ
// Hakem denetimi (docs/report/denetim-hakem.md §4.3) ön yüzde hiçbir
// statik kalite kapısı olmadığını buldu. Arka uçta `ruff` + `mypy`
// varken ön yüzde yalnızca `tsc` vardı — o da yalnızca tip hatası
// bulur, kullanılmayan değişkeni ya da kırık hook bağımlılığını değil.
//
// ⚠ Daha kötüsü: `npm run lint` betiği bir ara VARDI ama eslint kurulu
// değildi ve betik patlıyordu. CLAUDE.md o zaman şunu yazmıştı:
// *"Çalışmayan bir kalite kapısı, olmayan kapıdan kötüdür (yeşil
// sandırır)."* Betik kaldırılmıştı; şimdi kapının kendisi kuruluyor.
//
// ⚠ react-hooks kuralları BİLEREK hata seviyesinde: P-26 ve P-14
// hataları canvas/overlay çiziminden çıkmıştı ve o kod tam olarak
// hook bağımlılıklarının yanlış olabileceği yer.

import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // ⚠ Kullanılmayan değişken HATA, uyarı değil: ölü kod bu projede
      // defalarca "yapıldı sanılan ama bağlanmamış" iş oldu (P-43/44/45).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // `any` kaçışına izin verilmiyor — tip sistemi ancak delinmezse korur.
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  {
    // Test dosyalarında Vitest globalleri.
    files: ["**/*.test.{ts,tsx}", "**/test/**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
  },
);
