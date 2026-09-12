# A Twenty-Camera Real-Time Surveillance System on Constrained Hardware: A Case Study on the Measurability of Performance and Accuracy Claims

**Ömer Faruk Kanat**¹*

¹ Düzce University, Faculty of Engineering, Department of Computer Engineering, Düzce, Türkiye. `ror.org/04175wc52`

* Corresponding author: Ömer Faruk Kanat, omerfk0121@gmail.com
ORCID: 0009-0006-9229-6217

**Article Type:** Research Article

---

## ABSTRACT

This study examines whether performance values measured for individual computer vision components remain valid when they share a single hardware platform. The system presented here processes twenty concurrent camera streams on one mid-range laptop graphics processor (RTX 3070 Laptop, 8 GB), combining object detection, tracking, pose estimation, facial expression classification, anomaly detection and aggression estimation in a single pipeline. End-to-end latency was 378 ms (p50) and 652 ms (p95); the analysed frame rate remained at 2.34 frames per second per camera. For violence detection, averaging a skeleton-based gradient boosting model with a raw-pixel three-dimensional convolutional model gave an F1 of 0.937 (0.917 after correcting threshold selection bias); the gain is attributable to the two models' error sets overlapping by only 10%. For anomaly detection, fusion gave an area under the curve of 0.869 (95% cluster bootstrap interval 0.806 to 0.929), while a control series applying the same temporal smoothing to a single signal gave 0.860, showing that the gain comes from smoothing rather than from signal combination. The second contribution is methodological: in 43 of 87 development-log entries, a performance or accuracy claim was refuted by a later measurement. These refutations fall into three classes: a criterion whose attainable upper bound lies below its target, a threshold below the measuring instrument's resolution, and an observation unit violating the independence assumption. In security, although a single entry point was established, the endpoints passing through it were never enumerated; the observability interface was consequently reachable without authentication, and this was corrected.

**Keywords:** Multi-camera surveillance, Real-time video analytics, Violence detection, Resource-constrained inference, Measurement validity

> **Note on language.** This article was originally written in Turkish and subsequently translated into English by the author. In case of any discrepancy between the two versions, the Turkish version shall be taken as authoritative.

---

## I. INTRODUCTION

The automation of video surveillance systems is one of the most intensively studied application areas in computer vision. In object detection, multi-object tracking, pose estimation and video-based action recognition, significant progress has been recorded in recent years in terms of both accuracy and speed. When these components are evaluated individually, their per-frame costs and accuracy values are reported in detail.

Violence detection in surveillance video constitutes a distinct line of work within these application areas. Approaches fall into two main groups. The first group relies on features derived from the human skeleton and aims at real-time operation (Zhang et al., 2023; Mittal et al., 2026). The second group employs spatio-temporal networks that process video segments directly as raw pixels (Senadeera et al., 2024; Pathak et al., 2024). In video anomaly detection, approaches in which vision-language models are used in an unsupervised or weakly supervised manner have recently come to the fore (Zou et al., 2025; Shao et al., 2025; Borodin et al., 2025).

This study does not aim to select the individually best-performing of these approaches, but rather to operate several components together on a single hardware platform. For this reason, computational cost was as decisive as accuracy in component selection.

The starting point of this study is the question of whether component-level values transfer to an integrated system. The question was made concrete by a measurement taken during development. The object detection model used in this study consumes **3.78 ms** per frame when measured on a graphics processor dedicated solely to it and with fully populated batches. The same model consumes **7.46 ms** per frame when measured inside the twenty-camera pipeline while sharing the same hardware with the other stages (Table 7). The approximately twofold difference arises not from the model itself but from the context in which it runs: batches are not fully populated in production, the processor is shared with other stages, and the memory access pattern changes.

This observation is not confined to a single component. In an interventional experiment at the system level, doubling the frame rate acquired from the cameras did not increase the analysed frame rate but **reduced** it by 32% (Section III.A.3). No component-level measurement can predict this behaviour, because the behaviour arises not from the components themselves but from resource sharing.

The practical significance of this distinction emerges in the environments where surveillance systems are actually deployed. The resources available to small and medium-sized institutions are not a scalable cloud infrastructure but most often a single server or a single workstation. In such an environment, the answer to the question "can twenty cameras be processed in real time" depends less on the individual performance of the models used than on how those models are positioned together and at which points the system saturates.

### A. Scope and constraints of the study

This study was carried out within the scope of an internship project, over twenty-five working days, by a single developer and under the constraints set out below. The constraints are stated explicitly from the outset because they determine the conditions under which the results are valid.

**Hardware.** All measurements were performed on a single laptop computer: NVIDIA RTX 3070 Laptop GPU (8 GB VRAM), 20 logical processor cores, 16 GB system memory. The laptop variant offers approximately 65% to 75% of the performance of the desktop graphics processor bearing the same name and is subject to thermal throttling.

**Camera source.** No real IP cameras were used in this study. Twenty cameras were simulated by broadcasting video files compiled from different datasets in an infinite loop through a media server. The effect of this arrangement on the measurements is addressed quantitatively in Section III.C.3. In brief, raw rates of the "alarms per camera-hour" type become directly dependent on the length distribution of the source videos.

**Duration and scope.** The project was initially designed as an internship study, and the decision to convert it into an academic publication was taken at a later stage of development. This decision meant that measurement rigour was increased not throughout the project but only after a certain point in the process. Some of the early measurements were subsequently repeated; those that could not be reproduced are explicitly indicated in Section III.

**Limitations of the evaluation data.** The methodological claim of this study concerns the effect of measurement design on results; therefore the same standard must also be applied to this study's own evaluation data. The evaluation sets used are small, and this is directly reflected in the confidence intervals of the results: anomaly detection was measured over nine clips (1439 frames), violence detection over ninety-six clips, and alarm precision over nineteen independent events. For this reason point estimates are never reported alone throughout the study; every accuracy value is given together with a confidence interval, and the independence of the unit of observation was separately verified when computing those intervals (Section II.C.5). The claim of this study is not the general validity of the accuracy values obtained, but rather **a demonstration of the conditions under which and the uncertainty with which those values were obtained.**

### B. Contributions

The contributions of the study fall under four headings.

**(a) An architecture measured end to end on constrained hardware.** A pipeline based on cascaded filtering was designed, in which twenty camera streams are processed on a single graphics processor. The cost of each stage was measured separately on a per-frame basis, and the sum of the measured costs was verified to equal the independently measured loop total (Section III.A).

**(b) The gain from model combination and its mechanism.** The gain obtained by combining two independent violence detection models, one skeleton-based and one raw-pixel-based, was measured, and the source of this gain was shown to be that the error sets of the two models overlap by only 10%. The success of the combination was thereby moved from being an observation to being attributed to a mechanism (Section III.B.1).

**(c) The mismatch between criterion and data.** Here, a "criterion" is a numerical target defined in advance for the system to be considered successful; for example, "issue a warning at least 2 seconds before violence begins" is a criterion. In three criteria in this study, the reason the target was not met was shown to be not the performance of the system but the criterion itself. In one criterion, the highest attainable value in the dataset used lies below the target; in another, the criterion threshold falls below the resolution of the measuring instrument; and in the third, the unit of observation does not satisfy the independence assumption (Section III.C).

**(d) The inventory gap in a single entry point architecture.** In an architecture where authentication is concentrated at a single point, the observability interface was found to be unprotected because the inventory of endpoints passing through that point had not been enumerated; the recurring structure of the finding and the method of its remediation are documented (Section III.D).

### C. Organisation of the article

Section II introduces the system architecture, the datasets used, and the measurement methodology, which is treated as a separate heading in this study. Section III presents the performance, accuracy, criterion validity and security findings, and discusses the limitations in a separate subsection. Section IV contains the conclusions and suggestions for future work.

---

## II. MATERIAL AND METHOD

### A. System architecture

The system consists of five independent processes: acquisition, inference, analytics, alerting and the application programming interface. Communication between processes is provided by streams on an in-memory data structure server (Valkey). The overall flow is shown in Figure 1.

**[FIGURE 1]**
*Figure 1. System data flow and measured costs.*

Four rules derived directly from the hardware constraint were adopted in the architectural design.

**Raw video frames are not passed through the message queue.** A frame at 1080p resolution occupies approximately 6 MB. Writing this data to a message queue from twenty cameras at a rate of several frames per second turns the queue itself into a bottleneck. Instead, frames are written to shared memory and only a reference together with metadata is passed through the queue. The shared memory pool consists of 96 slots, each holding a complete 720p BGR frame (1280 × 720 × 3 bytes = 2.76 MB), and the pool occupies 265 MB in total. The size of the pool is not a storage decision but a queueing decision; the rationale is discussed in Section III.A.7.

**The server does not draw detection boxes onto the video image.** Video is delivered to the browser directly from the media server via a WebRTC-based protocol (WHEP), while detection boxes are sent in JSON format over a separate WebSocket connection and drawn in the browser. This separation makes it unnecessary to re-encode twenty separate video streams on the server side.

**Models are loaded once, in a single process.** The inference process holds the detection, pose and face models as single copies. Measured video memory usage is 571 MB (7% of 8192 MB).

**All queues are bounded.** An unbounded queue leads to memory exhaustion when the producer is faster than the consumer. In the system, older frames are dropped rather than waited for, and the number of dropped frames is separately measured.

#### A.1. Cascaded processing

Processing twenty streams on a single graphics processor is made possible by not applying every model to every frame. The pipeline is organised as a cascade (Figure 2).

**[FIGURE 2]**
*Figure 2. Cascaded processing and the measured cost distribution.*

**Stage 0, motion gate (processor).** Static scenes are eliminated by examining the difference between consecutive frames, and adaptive sampling is additionally applied on a per-camera basis. On a camera where no motion has been observed for an extended period, the sampling rate is reduced from 4 to 1 frame per second.

**Stage 1, object detection (graphics processor).** Only the person class is detected.

**Stage 1b, multi-object tracking.** A separate tracker instance is maintained for each camera (Aharon et al., 2022). In selecting the tracker, findings that approaches including low-confidence detections in the association stage improve identity stability were taken into account (Zhang et al., 2023b).

**Stage 2a, pose estimation (graphics processor).** Applied to each detected person box using a top-down approach.

**Stage 2b, face detection and expression classification.** A lightweight detector is used for face detection (Wu et al., 2023), while classification is thinned by a two-step gate (Section III.B.4). Integrated tools capable of real-time operation exist for facial behaviour analysis (Hu et al., 2025); the constraint in this study is not the model itself but the resolution of faces in surveillance imagery.

One planned stage was not implemented. The video-based action verifier, designed as Stage 3, was intended to pass a short video segment to a three-dimensional convolutional network when the escalation score exceeded a given threshold, in order to confirm or reject the alarm. The reason for its non-implementation is explained as a scope decision in Section III.E.

### B. Datasets and ground truth

The sources of the twenty-camera farm and the evaluation datasets are given in Table 1 and Table 2.

*Table 1. Source datasets of the camera farm.*

| Dataset | Cameras | Content | Purpose of use |
|---|---|---|---|
| VIRAT Ground 2.0 (Oh et al., 2011) | cam-01 to cam-08 | Fixed surveillance: car park, campus, building entrance | Learning the "normal" profile for the anomaly module |
| Oxford Town Centre (Benfold & Reid, 2011) | cam-09 | Dense pedestrian traffic, with ground truth | Tracking accuracy reference |
| PETS 2009 (Ferryman & Shahrokni, 2009) | cam-10 to cam-14 | Multi-camera crowds, sudden dispersal | Crowd and dispersal rules |
| UBI-Fights (Degardin & Proença, 2020) | cam-15 | Long-duration surveillance containing violence | Early warning, contextual measurement |
| UR Fall Detection (Kwolek & Kepski, 2014) | cam-16 | Controlled fall recordings | Validation of the fall rule |
| RWF-2000 (Cheng et al., 2021) | cam-17 | Surveillance-sourced fight clips | Aggression module |
| CUHK Avenue (Lu et al., 2013) | cam-18, cam-19 | Campus surveillance, frame-level labels | Anomaly control and test |
| Pexels | cam-20 | Scenes containing close-up faces | Expression module test |

The datasets were used within the framework of their own licence conditions and for research purposes only.

*Table 2. Evaluation datasets and the criteria they support.*

| Dataset | Label level | Size | Criterion supported |
|---|---|---|---|
| RWF-2000 validation | Clip | 96 clips | Violence detection F1 |
| RWF-2000, manually annotated | Frame (onset) | 20 fight clips | Early warning lead time |
| CUHK Avenue | Frame | 9 clips / 1439 frames | Anomaly detection AUC |
| Camera farm alarms | Event | 40 alarms, 19 independent events | Alarm precision |

Two label sets used in the evaluation were produced manually within the scope of this study.

**Violence onset labels.** In 20 fight clips selected from the RWF-2000 validation set, the frame at which violence begins was marked by a single annotator without viewing the system scores.

**Alarm validation labels.** For each of the 40 alarms produced by the system, a segment of approximately 6 seconds was extracted from the source video and it was assessed whether the alarm was justified. The assessment criterion was written before the segments were viewed and was derived, for each alarm type, from what the rule claims in the code. Three options were defined for the annotator: justified, false, and undecided. Because counting indecision as "false" would unfairly penalise the system while counting it as "justified" would favour it, a third option was considered necessary.

A known limitation of both label sets is that they were produced by a single annotator and that inter-annotator agreement was not computed.

### C. Measurement methodology

This section constitutes the methodological basis of the second contribution axis of the study. Each of the seven practices listed below was adopted following a concrete measurement error that arose during development.

**C.1. Taking window differences from cumulative histograms.** System measurements are collected through Prometheus-format histograms. These histograms are cumulative, that is, they count all observations from the start of the process. Reading a percentile directly from a cumulative histogram yields the percentile of the entire lifetime of the process rather than that of the measurement window. In this case the same system, with the same code and under the same load, produces different values depending solely on how long the process has been running. All percentile computations are performed over the difference between two snapshots taken at the beginning and the end of the window.

**C.2. Measuring processor time rather than wall-clock time.** Measuring a code section with a wall-clock counter also includes the time that section spends blocked. Furthermore, when the underlying numerical libraries use a thread pool, the wall-clock duration falls far below the total processor time consumed. Component costs are measured with `time.thread_time()`, over the processor time consumed by the relevant thread only.

**C.3. Closure check.** When the components of a pipeline are measured individually and summed, it is verified whether the resulting total equals the independently measured loop total. When this check is not performed, the cost of unmeasured components is implicitly assumed to be zero. The absence of this check in this study led to 70% of the pipeline cost being incorrectly reported as "unmeasured overhead" at one stage; the error introduced by this omission is addressed in Section III.A.4.

**C.4. Use of a control series.** To guard against the possibility that a measurement reflects the ceiling of the measuring instrument rather than that of the system being measured, a control measurement is taken without applying load. Two control series were defined in this study: the measurement taken with no cameras open in the interface fluidity measurement (Section III.C.2), and the single-signal series applying the same temporal smoothing as the fusion in the fusion evaluation (Section III.B.2).

**C.5. Determining the unit of independence.** When computing confidence intervals, the assumption that observations are independent is mostly invalid for video data, because consecutive frames from the same clip contain the same scene, the same people and the same lighting. In this study both frame-level and clip-level bootstrap intervals (Efron, 1979; Field & Welsh, 2007) were computed and reported. The difference between them is a quantitative measure of the effect of the independence assumption on the result.

**C.6. Measuring threshold selection bias.** For threshold-dependent metrics such as F1, searching for the best threshold within the same set on which the metric is computed produces an optimistic result. This bias was measured by repeatedly and stratifiedly splitting the dataset in half, selecting the threshold on one half and applying it to the other (400 repetitions). The optimism caused by performing model selection on the same set has been examined in detail in the literature (Varma & Simon, 2006).

**C.7. Winner's curse correction.** Selecting the best among several candidate rules on the same data makes the performance of the selected rule appear optimistic. This optimism was estimated by bootstrap and reported. In addition, the combination rule was determined before the measurement was performed.

Table 3 summarises the types of measurement error encountered in this study and the corresponding corrections.

*Table 3. Observed measurement error types and the corrections applied.*

| Error type | Symptom | Correction |
|---|---|---|
| Reading a percentile from a cumulative counter | Different results under the same conditions | Window difference (C.1) |
| Confusing wall-clock time with processor time | Cost appearing lower than it is | Thread time (C.2) |
| Two different units within the same metric | Component sum failing to match the loop total | Single unit with closure check (C.3) |
| Treating the unmeasured as zero | Unexplained cost remaining invisible | Closure check (C.3) |
| Mistaking the instrument ceiling for the system | Round values that raise no suspicion | Control series (C.4) |
| Treating dependent observations as independent | Confidence interval narrower than it should be | Cluster bootstrap (C.5) |
| Selecting the threshold on the measurement set | Optimistic F1 | Repeated half-splitting (C.6) |
| Selection among candidate rules | Optimistic best score | Winner's curse estimation (C.7) |

### D. Security approach

Security requirements were defined at the start of the project as a twenty-item prioritised list and were tracked throughout development. Authentication is built on passwords stored with Argon2id and short-lived JWT tokens, with tokens held in an `HttpOnly` cookie. Authorisation is enforced at every endpoint as a dependency, using a three-role model comprising viewer, operator and administrator.

The decisive component of the architecture from a security standpoint is the single entry point established through a reverse proxy. The application interface, the dashboard and the video stream are all served from the same origin; before forwarding each video request to the media server, the proxy redirects it to the application interface for an authorisation query (Figure 3). The vulnerability from which this design arose, and the deficiency it subsequently revealed, are addressed in Section III.D.

**[FIGURE 3]**
*Figure 3. Single entry point and authentication of the video stream.*

---

## III. RESULTS AND DISCUSSIONS

### A. Performance

The values measured for the system in steady state with twenty cameras are given in Table 4, compared against the success criteria.

*Table 4. Success criteria and measured values.*

| Criterion | Target | Measured | Status |
|---|---|---|---|
| Concurrent cameras | ≥ 20 | 20 / 20 | Met |
| Analysed frame rate (per camera) | ≥ 4 fps | 2.34 | Not met, cause measured |
| End-to-end latency | ≤ 1500 ms | p50 378 ms, p95 652 ms | Met |
| Two hours of uninterrupted operation | No interruption | 120 min, 0 interruptions | Met, earlier version |
| Violence detection F1 | ≥ 0.85 | 0.937 (bias-corrected 0.917) | Met |
| Anomaly detection AUC | ≥ 0.75 | 0.869 (cluster CI 0.806 to 0.929) | Met |
| Alarm precision | False alarms ≤ 3 per camera-hour | Precision 0.895 (CI 0.686 to 0.971) | Criterion redefined |
| Early warning lead time | ≥ 2 s | −1.10 s | Not met, criterion ceiling below target |
| Security priority list | 100% | 18 / 19 | Partially |
| Interface fluidity | ≥ 30 fps | Median 30.00 | Criterion not discriminative |

Two criteria fell below their targets, and the cause of both was measured. One criterion (alarm precision) was redefined, and another (interface fluidity) was found not to be measurable. The rationale for these four cases is presented in the subsections below.

#### A.1. The bottleneck is architectural, not in the hardware

The analysed frame rate falling below the target suggests at first sight an insufficiency of hardware. Measuring resource usage does not support this explanation (Table 5).

*Table 5. Resource usage in steady state (twenty cameras, dashboard closed).*

| Component | Memory (MB) | Processor (cores) | Threads |
|---|---|---|---|
| Acquisition | 1295.0 | 2.42 | 356 |
| Inference | 1077.2 | 0.89 | 7 |
| Analytics | 133.5 | 0.93 | 2 |
| Alerting | 57.9 | 0.00 | 2 |
| Application interface | 74.1 | 0.02 | 3 |
| **Total** | **2633.9** | **4.27** | |

Graphics processor utilisation was measured as a median of 28.5% (mean 26.7%, range 0% to 85%) over a window of sixty samples, and video memory usage as 571 MB (7% of the total 8192 MB). That is, while the system remains below target, approximately fifteen of the twenty logical cores, roughly seventy per cent of the graphics processor and ninety-three per cent of the video memory remain unused.

The limiting factor is that the main loop of the inference process is serial. The loop processes a batch from beginning to end, using a single core while doing so. The measured value is 0.89 cores and does not rise above this value regardless of load. Waiting time was separately measured and found to be 1.69 ms per frame; that is, the process is not idle but is doing work approximately ninety-three per cent of the time.

#### A.2. The gap between supply and demand

The acquisition process publishes 56.8 frames per second while the inference process can handle 46.8. Of the 11501 frames published during the measurement window, 2017 (17.5%) remained in the queue without being analysed. This gap was not visible until frame accounting was added: the dropped-frame counter was counting only cases where no shared memory slot could be found, and not frames evicted at the queue ceiling.

#### A.3. Increasing the input reduced the output

The saturation point cannot be determined from observational data. The reason is that when the system is fed more slowly than the consumer can process, the measured throughput reflects the speed of the producer rather than the capacity of the consumer. To make this distinction visible, an interventional experiment was performed: the target sampling rate per camera was increased from 4 to 8 frames per second and the measurement was repeated (Table 6).

*Table 6. Effect of doubling the sampling rate.*

| Metric | 4 fps | 8 fps | Change |
|---|---|---|---|
| Published (per camera) | 2.78 | 4.37 | Increased |
| **Analysed (per camera)** | **2.78** | **1.88** | **Decreased by 32%** |
| Latency p50 (ms) | 173 | 433 | Increased 2.5-fold |
| Untracked frame loss | Approximately 0% | 56.9% | |
| Consumer lag (entries) | 0 | 40 | Genuine backlog |
| Acquisition processor usage (cores) | 2.10 | 3.79 | Increased |
| Inference processor usage (cores) | 0.89 | 0.89 | **Unchanged** |

The result is counter-intuitive: sending more frames did not produce more analysis but instead reduced the number of frames analysed. The mechanism is visible in the measurement. The processor usage of the acquisition process rose from 2.10 to 3.79 cores, while that of the inference process remained constant. The increased acquisition load steals time from the inference process, which shares the same processors. In addition, because the queue fills, frames are evicted without being analysed, and the surviving frames wait longer, so latency increases.

This experiment is the system-level counterpart of the argument advanced in the introduction. No component-level measurement can predict that increasing the input will reduce the output, because this behaviour arises not from the components themselves but from resource sharing.

#### A.4. Stage breakdown of the inference loop and the closure check

To determine at which stage the bottleneck lies, each stage of the inference loop was measured separately. Two rules were applied in the measurement. The first is that all stages are read in the same unit (milliseconds per frame) and within the same time window. The second is that the sum of the stages is compared against the independently measured loop total. The results are given in Table 7.

*Table 7. Stage breakdown of the inference loop (120 s, 863 batches, 6.5 frames per batch).*

| Stage | ms/frame | Share |
|---|---|---|
| Pose estimation | 10.96 | 48% |
| Object detection | 7.46 | 33% |
| Tracking | 1.56 | 7% |
| Publishing | 1.24 | 5% |
| Serialisation | 0.56 | 2% |
| Face and expression | 0.46 | 2% |
| Slot release | 0.37 | 2% |
| Shared memory read | 0.00 | 0% |
| **Sum of measured stages** | **22.62** | |
| **Independently measured loop total** | **22.65** | |
| **Unexplained** | **0.04** | **0%** |

The last three rows constitute the actual value of this table. The sum of the components equals the independently measured loop total to within 0.04 ms; that is, the entire loop has been accounted for. This check was not performed in an earlier measurement, and as a result an incorrect finding was produced to the effect that seventy per cent of the loop cost was "unmeasured overhead". In reality the measurement tool was summing two different units under the same metric: some stages were recording per frame and others per batch. When the closure check was added, the error became visible in the first run.

The table is also the source of the observation presented in Section I. Object detection here consumes 7.46 ms per frame; the same model consumes 3.78 ms under isolated conditions with a fully populated batch (Table 8).

The same breakdown was repeated one day later with a different measurement script. In the second measurement the stage sum was 23.22 ms, the loop total 23.26 ms, and the gap again 0.04 ms. This repetition shows that the table is not an artefact of a single run.

#### A.5. Inference engine acceleration attempt

Table 7 shows that the accelerable graphics processor work constitutes eighty-one per cent of the loop budget (pose 48%, detection 33%). For this reason acceleration with TensorRT was measured (Table 8).

*Table 8. Comparison of PyTorch and TensorRT (isolated measurement).*

| | Batch (ms) | Frame (ms) | p90 (ms) |
|---|---|---|---|
| PyTorch FP16 | 30.233 | 3.779 | 31.324 |
| TensorRT FP16 | 18.741 | 2.343 | 20.310 |
| Speed-up | 1.61-fold | | |

It was additionally verified that the speed-up was obtained without degrading accuracy. Both engines produced twenty detections on the same image, the match was exact, and the mean intersection over union was 0.9915. This check is essential, because a speed-up can also be obtained by degrading the result.

The engine could not, however, be brought into production. Because the attention blocks of the detection architecture used could not find TensorRT kernels for dynamic input shapes, the engine had to be exported with a fixed batch size, which means that only fully populated batches of eight frames are accepted. The median batch size measured in production is 6.67 frames, and partial batches produce errors. It is possible to pad the missing places by repeating frames; in that case the effective gain falls from 1.61-fold to approximately 1.34-fold, and the throughput gain to approximately nine per cent. The results of the padded frames must then be filtered out, and if done incorrectly the system produces detections that do not exist. Within the remaining time this risk was not taken for a nine per cent throughput gain, and the decision was recorded with its rationale.

#### A.6. Parallelisation of the inference process was attempted

The finding in Section III.A.1 directly suggests a solution: if the inference process saturates on a single core, the cameras can be distributed across several inference processes. This option was implemented and measured.

The reason the option remained unconsidered for a long time is a design rule laid down at the start of the project: models were to be held as a single copy in a single process, on the assumption that video memory would otherwise be insufficient. This assumption had never been measured. When measured, a single process was found to use 571 MB and two processes 1134 MB in total; that is, the initial estimate was approximately eight times the actual value. A rule resting on an unmeasured figure kept an architectural option closed for a long period.

**The first implementation destroyed half of the frames.** The simplest approach was tried: all processes read the same message stream, and each process discarded frames belonging to cameras not assigned to it. The measurement showed that of 5236 frames published in a ninety-second window, only 2626 were analysed. The reason is that in the stream structure used, each message is delivered to only **one** consumer in the consumer group; a process discarding a frame not belonging to it does not pass that frame to the other, but destroys it.

The important aspect of this error is that the metrics appeared to improve:

*Table 9. Effect of the faulty distribution implementation.*

| Metric | Single process | Faulty distribution |
|---|---|---|
| Throughput (frames/s) | 46.3 | 28.0 |
| Latency p50 (ms) | 172 | 104 |
| Latency p95 (ms) | 322 | 238 |

When half the work is discarded the queue empties and latency falls. An evaluation looking only at latency would interpret this as a success. The error became visible only because the published and analysed frame counts were counted separately. An improvement in a metric does not mean that the system has improved.

**In the correct design, routing was moved to the producer side.** The acquisition layer writes each camera to a sub-stream derived from a checksum of the camera name, and each inference process reads only its own sub-stream. Each frame is thereby processed in exactly one stream and one process. A checksum function that does not vary between processes was chosen; because the language's built-in hash function is randomised across processes, the acquisition and inference processes would have produced different results and cameras would have disappeared silently. It is also mandatory that a given camera always goes to the same process, because tracking state is maintained per camera within the process.

**The measurement of the corrected implementation** is given in Table 10.

*Table 10. Measured effect of distribution (single process versus two processes).*

| Metric | Single process | Two processes | Change |
|---|---|---|---|
| Throughput (frames/s) | 45.1 | 53.7 | 19% increase |
| Latency p50 (ms) | 359 | 183 | 49% decrease |
| Latency p95 (ms) | 638 | 411 | 36% decrease |
| Inference processor (cores) | 0.90 | 1.77 | Twofold |
| Video memory (MB) | 571 | 1134 | Twofold |
| **System memory usage** | **84%** | **98%** | |

That both inference processes saturate at 0.89 cores confirms, on a per-process basis, the single-core ceiling observed in Section III.A.1. That the gain in throughput is not twofold is an expected result: distribution removed the limit on the inference side, and the constraint moved to the acquisition layer and the shared memory pool.

**The option was nevertheless not enabled in production.** The reason is system memory: with two processes, usage rises to 98%, and on a machine with sixteen gigabytes this limit is not safe for long-running operation. Moreover, after the shared memory pool was enlarged, the throughput of the single-process configuration caught up with the two-process configuration; that is, part of the bottleneck that distribution was attempting to solve was removed by a cheaper correction.

**A known limitation of the measurements in this subsection.** The output files of the distribution comparison and of the pool size comparison were not saved; the values were recorded only in the development log. Measurements made on subsequent days with the same configuration did not reproduce these values exactly. The values are reported in terms of their direction and order of magnitude, whereas the figures used in the other sections of the article are taken from measurements whose outputs were preserved. This distinction is a concrete instance, within this study, of the record-keeping problem addressed in Section III.E.

#### A.7. The size of the shared memory pool is a queueing decision

The shared memory pool consists of ninety-six slots and occupies 265 MB. Given that system memory is 16 GB, this value appears low. The function of the pool is buffering rather than storage: the slots hold only frames in flight between acquisition and inference. As long as the inference process keeps up, the number of slots in use at any one time is small.

Enlarging the pool ceases to be beneficial beyond a certain point. If the consumer is saturated, a larger buffer does not increase throughput but merely causes the frames waiting in the queue to be older, and therefore increases latency. This behaviour is a known result in queueing theory and was also observed in the system (Section III.A.3).

During development, a clear improvement was observed when the pool size was increased from forty-eight to ninety-six slots. The reason is that forty-eight was too small and the producer was dropping frames because it could not find a slot. A note on honesty is required here, however: the measurement output for this comparison was not saved to file but was recorded only in the development log. Measurements made the following day with the same configuration did not reproduce those values. For this reason, the measurements used in this article are those that are reproducible and whose outputs are preserved; values that could not be reproduced are not used.

### B. Accuracy

#### B.1. Violence detection and the combination of two models

Three approaches to violence detection were developed and evaluated in turn.

**The first is a rule-based approach.** Quantities such as wrist speed, torso inclination, motion energy and inter-person proximity were derived from the joint positions obtained from pose estimation, and these were combined using manually determined weights. This approach was evaluated on a subset of one hundred and twenty clips consisting of sixty fight and sixty normal clips, and yielded an area under the curve between 0.62 and 0.66 and an F1 score of around 0.71. The value obtained was used as the baseline that subsequent models had to exceed.

Why the rule-based approach remained limited was also examined. The weights rest on the assumption that violence involves fast and abrupt movement. The measurement does not support this assumption: a significant proportion of the genuine violence events in the dataset take the form of grappling, and the movement speed measured during grappling can be lower than that of normal walking within a crowd. Manually written weights encode an unmeasured intuition.

**The second is an approach that feeds the same skeleton features to a gradient boosting model (Ke et al., 2017) rather than to manually determined weights.** The features are identical; only the way they are combined changes.

**The third is a three-dimensional convolutional network that processes short video segments directly as raw pixels (Tran et al., 2018).** This approach does not depend on skeleton extraction at all and can therefore operate in cases where pose estimation fails.

The results of the second and third approaches, together with their combinations, are given in Table 11.

The rule-based approach does not appear in Table 11. The reason is that it was evaluated on a different subset (one hundred and twenty clips). Comparing values obtained on different evaluation sets within the same table is one of the error types criticised in Section II.C of this study; the rule-based result is therefore given in the text together with its own sample size.

*Table 11. Violence detection results (RWF-2000 validation, 96 clips).*

| Model | AUC | AUC 95% CI | F1 | Precision | Recall |
|---|---|---|---|---|---|
| Skeleton and gradient boosting | 0.9267 | 0.8676 to 0.9722 | 0.8889 | 0.9565 | 0.8302 |
| Raw pixel (3D convolution) | 0.9366 | 0.8820 to 0.9796 | 0.9107 | 0.8644 | 0.9623 |
| **Combination (mean)** | **0.9684** | **0.9352 to 0.9917** | **0.9369** | 0.8966 | 0.9811 |
| Combination (maximum) | 0.9636 | 0.9257 to 0.9909 | 0.9358 | 0.9107 | 0.9623 |
| Combination (minimum) | 0.9381 | 0.8868 to 0.9770 | 0.8889 | 0.8727 | 0.9057 |
| Combination (product) | 0.9561 | 0.9168 to 0.9850 | 0.9009 | 0.8621 | 0.9434 |

The combination yields a result 0.032 AUC points higher than the best single model. Three additional checks were performed so that this difference could be reported.

**Threshold selection bias.** The F1 values are obtained by searching for the best threshold on the same set and are therefore optimistic. The optimism measured by four hundred repetitions of stratified half-splitting is 0.0204 points for the combination; that is, 0.9165 instead of 0.9369. The optimism of the other models lies between 0.018 and 0.033. Both values are given in the article.

**Winner's curse.** Selecting the best among four different combination rules on the same data makes the performance of the selected rule appear optimistic. This optimism was estimated by bootstrap at 0.0014 AUC points. In addition, since the averaging rule had been determined before the measurement was performed, this effect is minimal.

**The mechanism of the gain.** That the combination gives a better result is not in itself an explanation; it must be shown why the two models complement each other. The error sets were compared. There are ten clips on which only the skeleton-based model errs, nine clips on which only the raw-pixel model errs, and only one clip on which both err. The overlap rate is ten per cent. The models err on different clips rather than the same ones, and the gain of the combination originates here. This measurement moves the combination from being an observation to being attributed to a mechanism.

**Computational cost.** The cost of the raw-pixel model for one window is 6.44 ms. For twenty cameras this corresponds to approximately 354 ms per second, which fits within the real-time budget.

#### B.2. Anomaly detection and testing the fusion

Anomaly detection is based on the weighted combination of five signals. This combination is referred to in this study as fusion and operates as follows. For each tracked person, signals for aggression (weight 0.40), deviation from the learned camera profile (0.25), physical rule violation (0.20), facial expression (0.10) and crowd density (0.05) are produced between zero and one, their weighted sum is taken, the result is temporally smoothed by an exponential moving average, and hysteresis is applied to convert it into a single risk score. Temporal smoothing means blending the score computed in each successive window with the previous value rather than using it directly; the aim is to prevent a single noisy window from triggering an alarm.

In order to measure the contribution of the fusion, a control series was defined: the same temporal smoothing as the fusion is applied to a single signal. Two variables are thereby separated: combination and smoothing. The results are given in Table 12.

*Table 12. Anomaly detection results (CUHK Avenue, 9 clips and 1439 frames).*

| Signal | AUC | Frame-level CI | Clip-level CI |
|---|---|---|---|
| **Fusion (5 signals and smoothing)** | **0.8691** | 0.8257 to 0.9060 | **0.8057 to 0.9286** |
| Profile deviation, raw | 0.7891 | 0.7476 to 0.8250 | 0.7494 to 0.8275 |
| **Profile deviation and smoothing (control)** | **0.8602** | 0.8128 to 0.9019 | 0.8142 to 0.9004 |
| Physical rules | 0.500 | | 0.499 to 0.500 |
| Aggression | 0.457 | | 0.444 to 0.486 |

The difference between the fusion and the control series is 0.0089 points. The significance threshold was set at 0.02 before the measurement was performed; the rationale is that the AUC uncertainty over nine clips and sixty-nine anomaly frames is of this order. The difference falls below this threshold.

The honest inference in this case is that what provides the gain in this dataset is temporal smoothing rather than signal combination. Moving from raw profile deviation to smoothed profile deviation gains 0.071 points, whereas combining five signals adds 0.009 points.

This result does not mean that the fusion is unnecessary; the condition under which the result holds must be stated. In the dataset used, two of the five signals are inoperative. The AUC of the physical rule signal is exactly 0.500, that is, it never fires. The reason is that the anomalies in that dataset are events such as throwing a bag, cycling and walking in the wrong direction, whereas the rules in this study are defined over human motion. The value of the aggression signal, at 0.457, is below chance level. Combining inoperative signals cannot be expected to produce a gain. The measured principal contribution of the fusion lies not in discriminative power but in noise suppression, and this contribution was observed in the alarm rate measurement.

#### B.3. Alarm precision

How many of the alarms produced by the system were justified was measured by manually evaluating segments extracted from the source videos. Thirty-nine of the forty alarms were labelled; for one no decision could be reached and it was excluded from the analysis.

The raw figure cannot be reported directly, because the source videos are broadcast in a loop and the same event produces alarms repeatedly. The alarms were deduplicated according to their position within the source video; alarms closer than six seconds to one another, belonging to the same camera and the same type, were counted as a single event. The results are given in Table 13.

*Table 13. Alarm precision (Wilson 95% confidence interval; Wilson, 1927).*

| | n | Correct | Precision | 95% CI |
|---|---|---|---|---|
| Raw labelled alarms | 39 | 37 | 0.949 | 0.831 to 0.986 |
| **Independent events** | **19** | **17** | **0.895** | **0.686 to 0.971** |
| Crowd | 9 | 9 | 1.00 | 0.70 to 1.00 |
| Combined risk | 5 | 5 | 1.00 | 0.57 to 1.00 |
| **Fall** | **5** | **3** | **0.60** | **0.23 to 0.88** |

The aggregate precision value is 0.895, but examining it by type shows that the distribution is not uniform. There are no errors in the crowd and combined risk types. Both false alarms are of the fall type and both arise from the same mechanism: a person bending down and lying on the ground is classified as a fall. The safeguard defined for the rate of change of torso inclination in the fall rule is insufficient to eliminate this movement.

This decomposition shows that an aggregate figure can conceal a finding. Had only the value 0.895 been reported, it would not have been apparent that the weak link of the system is a specific rule.

No measurement could be made for the loitering type. This rule is based on a forty-five-second observation window, whereas the evaluation segments are six seconds long. A six-second segment cannot validate a forty-five-second rule. This type is reported as zero samples, not as error-free.

This method measures precision only, that is, how many of the alarms produced by the system are correct. Recall was not measured; determining the events missed by the system would have required labelling the entirety of the source videos. This limitation must be taken into account when interpreting the results.

#### B.4. The effective coverage of the expression stage

Facial expression classification is thinned by a two-step gate. The first step requires the height of the person box to exceed one hundred and eighty pixels; the second requires face detection to succeed. In a measurement over twenty-one cameras and twenty-five frames per camera, 171 of 2087 person detections (8.2%) passed the first step. At the second step, no face could be detected on seven of the eight cameras that passed the first step; faces could be found only on the camera containing close-up faces.

This result has two implications. First, the low computational cost of the expression stage (0.46 ms per frame, two per cent of the loop) is not an efficiency achievement but a consequence of the gate eliminating almost everything. Second, and more importantly, the expression signal is in practice produced on a single camera. Since the fusion evaluates a missing signal as zero, this means that the expression weight is effectively disabled on the other cameras. This result holds for the camera farm and gate thresholds used. The measurement does not show that the expression stage is generally inoperative, but that the image resolution in this setup does not produce faces large enough to pass the gate. That the gate is passed completely on the camera containing close-up faces (faces found in 25 of 25 crops) supports this interpretation.

### C. The mismatch between criterion and data

This section presents the most original finding of the study. In three success criteria, the reason the target was not met is not the performance of the system but the criterion itself. The three cases are of different types and together yield a general rule.

#### C.1. The upper bound of the criterion lies below the target

The early warning criterion requires a warning to be issued at least two seconds before violence begins. The measurement results are given in Table 14.

*Table 14. Early warning lead time (RWF-2000, 20 fight and 30 normal clips).*

| Threshold | Caught | Missed | Late | Median lead | 95% CI | False alarms |
|---|---|---|---|---|---|---|
| 0.10 | 7 | 13 | 6 | −1.10 s | −1.87 to −0.07 | 13% |
| 0.15 | 4 | 16 | 4 | −1.72 s | −2.13 to −0.60 | 7% |
| 0.20 | 2 | 18 | 2 | −3.72 s | −4.30 to −3.13 | 3% |
| ≥ 0.25 | 0 | 20 | 0 | Not measurable | | ≤ 3% |

Negative values mean that the warning was produced after the event. As the threshold is lowered the lead improves but false alarms increase; this is an expected trade-off.

The principal finding does not lie in this table itself. The highest value attainable by the criterion on this dataset was computed: the median context duration before the onset of violence in the clips is 0.58 seconds and the maximum is 3.07 seconds. In only two of the twenty clips is a two-second lead physically possible. Moreover, the annotator who produced the labels reported that the marking includes their own reaction time and that violence in fact begins between zero and half a second. The true upper bound of the criterion is therefore even lower than the computed value.

Under these conditions, even a perfectly functioning detector cannot satisfy the criterion. The negative value obtained indicates not a failure of the system but a mismatch between criterion and data.

The finding was also tested on a second dataset of a different character. In a clip consisting of long-duration surveillance recordings and containing fifty-eight seconds of context before the event, the model is able to distinguish the moment of the fight from normal behaviour (median score ratio 2.756). In contrast, the escalation window leading up to the fight is scored lower than the normal sections (0.184 versus 0.282), and detection occurs 1.76 seconds after the event. The two datasets arrive at the same conclusion by different routes: the system detects violence but does not distinguish the escalation preceding violence.

#### C.2. The criterion threshold lies below the measurement resolution

The interface fluidity criterion requires the drawing rate to be at least thirty frames per second with twenty cameras open. The results of seven independent runs are given in Table 15.

*Table 15. Interface fluidity measurements (seven runs).*

| Metric | Median | Range |
|---|---|---|
| Drawing rate (fps) | 30.00 | 29.43 to 30.02 |
| Control, with no cameras open | Approximately 60 | 59.7 to 60.2 |
| Video decoding (total fps) | 225.0 | 200 to 300 |
| Dropped frame rate | 2.3% | 0.0% to 33.4% |

The drawing rate measurement depends on the vertical synchronisation of the browser and, on a sixty-hertz display, takes discrete values such as 60, 30, 20 and 15 in practice. Under load the browser drops from sixty to thirty and locks there. That the control series was measured at around sixty in every run supports this interpretation.

The threshold of the criterion is exactly thirty, that is, it sits on the discrete step at which the system settles. Whether the measured value comes out as 29.43 or 30.02 is determined not by the performance of the system but by the edge effects of the counting window. Under these conditions the decision "met" or "not met" changes with measurement noise, and the criterion is not discriminative.

The more informative quantity is the dropped frame rate, which varies between zero and thirty-three per cent across runs. This variability depends on the concurrent load on the machine. In an early measurement this rate was found to be zero and was interpreted as a better-than-expected result; the distribution over seven runs invalidates this interpretation. A result based on a single observation, particularly when it turns out better than expected, should not be accepted without repetition.

#### C.3. The unit of observation does not satisfy the independence assumption

The false alarm criterion allows at most three false alarms per camera per hour. This criterion does not measure the behaviour of the system in a setup where the source videos are broadcast in a loop.

The durations of the source videos vary between five and three hundred and forty-five seconds. A single fall event present in the shortest source replays approximately seven hundred and twenty times per hour and produces an alarm on each pass. The same system, the same algorithm and the same event produce seven hundred and twenty alarms per hour on a five-second source and twelve on a three-hundred-second source. The raw rate therefore reflects the length distribution of the test videos rather than the false alarm behaviour of the system.

For this reason the criterion was redefined as precision per independent event rather than an hourly rate. Thirty-nine labelled alarms, when deduplicated according to their position within the loop, correspond to nineteen independent events.

The same problem is present in the evaluation datasets. Anomaly detection is measured over 1439 frames, but these frames come from only nine clips, and consecutive frames of the same clip are not independent observations. The confidence interval computed at the frame level has a width of 0.080, whereas the interval computed at the clip level has a width of 0.123. The naive method claims a precision that is not possessed.

*Table 16. Three types of mismatch between criterion and data.*

| Type | Symptom | Example in this study | Consequence |
|---|---|---|---|
| Criterion upper bound below target | Even a perfect system cannot pass | Early warning: ceiling 0.58 s, target 2 s | Criterion not measurable on this dataset |
| Threshold below measurement resolution | Decision changes with noise | Interface fluidity: threshold 30, step 30 | Criterion not discriminative |
| Dependent unit of observation | Interval narrower than it should be, rate inflated | Alarm rate and frame-level AUC | Unit must be redefined |

These three cases together yield a practical rule. Before a criterion is reported, three questions should be asked: What is the highest value this criterion can attain with the data used? Is the criterion threshold above the resolution of the measuring instrument? Is the unit of observation genuinely independent?

### D. Security findings

#### D.1. The divergence between the protected surface and the surface requiring protection

The first finding identified during development is that, although the application programming interface was protected by authentication, the video stream was not. Accessing the imagery required only knowledge of the address. The first remedy was a network restriction: the relevant port was bound to the local interface. This does not close the vulnerability but merely limits access to the same machine; any process running on the machine can still obtain the imagery. The permanent solution is that the video stream be served from the same origin as the application and that the proxy perform an authorisation query against the application interface for every video request.

#### D.2. Establishing a single entry point is not sufficient; what passes through it must be enumerated

The second finding emerged after the single entry point had been established. The general forwarding rule in the reverse proxy configuration also exposes the application's endpoints that lack authentication. The audit found that the observability interface was accessible without authentication and through the single entry point. This interface contains camera names, alarm counts per camera, frame rates, latency distributions and an endpoint inventory. In a surveillance system this information is of a nature that could be used for reconnaissance before access to the system is obtained.

The finding was remedied by closing the endpoint in question at the proxy level. Adding authentication at the application level was not preferred, because the measurement collection process uses this interface locally and without passing through the proxy; protection at the application level would have broken observability. The correct layer is the outward-facing layer.

A second observation was also made during the audit. The tool used in the first pass of the audit enumerated endpoints by traversing the object graph of the application framework and found ten endpoints. However, endpoints added through sub-routers do not appear in this traversal; the true number is sixteen. The tool could not see part of the surface and did not report this. The method was therefore changed: unauthenticated real requests were sent to all endpoints obtained from the interface definition and the returned status codes were recorded. The tool that produces the inventory must itself also be verified.

#### D.3. Configuration producing false declarations

The third finding is that the configuration file contained settings with no counterpart in the code. Eleven of sixty-nine settings were not read on any code path. Two of these are directly in the nature of security declarations: one suggests that signed and time-limited clip links are configured, and the other that request rate limiting exists across the whole application interface. In reality the signed link feature was not implemented, and rate limiting exists only on the login endpoint.

This is not a code error, since no functionality is broken. However, an auditor examining the configuration file would conclude that protections not present in the system had been configured. The settings in question were therefore marked with an explicit statement that they are not implemented.

*Table 17. Status of the security priority list.*

| Status | Number of items | Scope |
|---|---|---|
| Implemented | 18 | Including password storage, token management, role-based authorisation, login rate limiting, audit logging, path traversal protection, transport layer security and single entry point |
| Out of scope, with justification | 1 | Per-camera authorisation; has no counterpart in a single-operator deployment |
| No attack surface formed | 1 | Server-side request forgery filter; since there is no camera-adding interface, there is no attack surface |

### E. Classification of the development log

In this study, every problem encountered during the development process was recorded on the same day in an engineering log. The log contains eighty-seven entries. Presenting all of these as methodological findings would not be correct; the entries differ in content.

The entries were divided into three groups. The first group consists of entries in which a performance or accuracy claim was refuted by a subsequent measurement, and contains forty-three entries. The second group consists of thirty-five entries that do not contain a claim refuted by measurement but are nevertheless findings at the architectural or implementation level. The third group comprises installation and environment problems and contains nine entries; matters such as port conflicts and version manager configuration fall into this group. The third group is not presented as findings in this article.

The methodological contribution axis of this article rests on the first group. What these forty-three entries have in common is that the error lay not in the model or the system but in the measurement chain. The most frequently occurring subtypes are listed in Table 3.

### F. Limitations

The results of this study should be assessed within the following limitations.

**No real cameras were used.** Twenty cameras were simulated from video files broadcast in a loop. This arrangement does not represent network behaviour, the variability of camera hardware, or the connection interruptions encountered in real deployments.

**The evaluation sets are small.** Anomaly detection was measured over nine clips, violence detection over ninety-six clips, and alarm precision over nineteen independent events. The confidence intervals are therefore wide and are given with every result in the article.

**Labelling was performed by a single annotator.** Inter-annotator agreement was not computed. That the early warning labels include human reaction time is documented by the annotator's own statement.

**Recall was not measured.** The alarm evaluation examines only the alarms produced and does not cover missed events.

**The endurance measurement belongs to an earlier version.** The two-hour uninterrupted operation test was performed on a code version preceding more than twenty subsequent changes and was not repeated.

**Some source videos are compilations.** Some sources in the camera farm were formed by concatenating several scenes. This strains the assumption that "each camera's own normal is learned", because the normal learned on such a source is the average of mutually unrelated scenes.

**Measurements were made on a single hardware platform.** How the results transfer to different graphics processors or numbers of processor cores was not measured.

**Component excluded from scope.** The video-based action verifier planned as Stage 3 was not implemented. The function of this stage was to confirm or reject an alarm by passing a short video segment to a three-dimensional convolutional network when the escalation score exceeded a threshold. The rationale for its non-implementation is twofold. First, the model in question had already been trained in this study and used for violence detection (Section III.B.1), but connecting it to the live pipeline as a verification stage requires triggering logic, segment buffering and an alarm retraction flow. Second, the available measurements show that alarm precision is already at 0.895 and that false alarms are concentrated in a single rule type; in that case a more targeted correction is more efficient than a general verification stage.

---

## IV. CONCLUSION

In this study, a surveillance system was developed in which twenty concurrent camera streams are processed on a single mid-range laptop graphics processor, and the performance and accuracy of the system were measured. The system combines detection, tracking, pose estimation, facial expression classification, anomaly detection and aggressive behaviour estimation within a single cascaded pipeline.

Two results stand out on the performance side. The first is that end-to-end latency remains well below the target (p50 378 ms, target 1500 ms). The second is that the analysed frame rate does not reach its target (2.34 frames per second, target 4). The cause of the second result was measured and is not a hardware insufficiency: graphics processor utilisation remains at a median of twenty-eight per cent and video memory usage at seven per cent, while the serial main loop of the inference process saturates on a single core. That the limiting factor is architectural was confirmed by an interventional experiment in which the sampling rate was doubled; when the input was increased, the analysed frame rate did not increase but fell by thirty-two per cent.

On the accuracy side, combining two independent models gained 0.032 area-under-the-curve points in violence detection relative to the best single model. The source of this gain was also demonstrated: the error sets of the models overlap by only ten per cent. In anomaly detection, by contrast, the gain from combining five signals fell below the significance threshold determined in advance when compared with a single-signal control series applying the same temporal smoothing. These two results together show that combination does not produce a gain of its own accord, and that the gain depends on the independence of the components being combined.

The targets that were not reached, and their reasons, should be stated explicitly. The analysed frame rate target was not met because of the serial inference loop. The early warning target could not be measured because the highest value attainable on the dataset used lies below the target. The interface fluidity target was found not to be discriminative because the criterion threshold falls on the resolution step of the measuring instrument. What these three cases have in common is that the outcome was determined more by the design of the criterion than by the performance of the system.

A generalisable rule follows from this. Before a success criterion is reported, three of its properties should be verified: the highest value the criterion can attain with the data used, the position of the criterion threshold relative to the resolution of the measuring instrument, and the independence of the unit of observation. When these checks are not performed, the figure obtained may not be wrong, but it may be answering the wrong question. In this study this was the case for all three criteria.

On the security side, two findings display the same pattern. In the first, the application interface was protected while the video stream was not; in the second, a single entry point was established but the inventory of endpoints passing through it was not enumerated. In both cases what was missing was not a security control but an inventory of the surface requiring protection. This observation indicates that checklist-based security approaches need to be complemented by surface enumeration.

Three directions stand out for future work. The first is the use of a dataset containing pre-event context so that the early warning criterion can be meaningfully evaluated; it was shown by measurement that neither of the two datasets used in this study possesses this property. The second is that labelling be performed by multiple annotators and that inter-annotator agreement be reported. The third is that the system be validated under real network conditions and with real cameras.

---

## DECLARATIONS

**Acknowledgements.** I thank Dr. Ahmet Albayrak of Düzce University for his guidance during the conduct of the study and for his suggestion that it be turned into an academic publication.

**Author contributions.** I carried out all parts of the study myself.

**Conflict of interest.** I declare that there is no conflict of interest.

**Supporting organisation.** I received no external funding for this research.

**Ethics approval.** This study does not involve human or animal participants. All video data used were obtained from academic datasets available for research purposes, and the relevant sources are indicated by citation. The datasets were used within the framework of their own licence conditions and for research purposes only.

**Plagiarism statement.** This article was evaluated with plagiarism detection software and no plagiarism was detected.

**Use of artificial intelligence tools.** A large language model based artificial intelligence tool (Anthropic Claude) was used in the conduct of this study and in the preparation of the article. The tool was used in software development, in writing the measurement scripts, in analysing the measurement results, and in drafting the article text. I ran all measurements presented in the article on my own hardware, preserved the resulting output files, and verified every numerical value in the text against those outputs. The final form of the text, its scientific content and its conclusions are my responsibility.

**Code availability.** The source code, measurement scripts and measurement outputs developed in the study are collected in a code repository: https://github.com/0merf/Staj-Proje

---

## REFERENCES

Aharon, N., Orfaig, R., & Bobrovsky, B.-Z. (2022). BoT-SORT: Robust associations multi-pedestrian tracking. *arXiv preprint*, arXiv:2206.14651.

Benfold, B., & Reid, I. (2011). Stable multi-target tracking in real-time surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 3457-3464.

Borodin, K., Kondrashov, K., Vasiliev, N., Gladkova, K., Larina, I., Gorodnichev, M., & Mkrtchian, G. (2025). Benchmarking compact VLMs for clip-level surveillance anomaly detection under weak supervision. *Journal of Imaging*, 11(11), 400.

Cheng, M., Cai, K., & Li, M. (2021). RWF-2000: An open large scale video database for violence detection. *25th International Conference on Pattern Recognition (ICPR)*, 4183-4190.

Degardin, B., & Proença, H. (2020). Human activity analysis: Iterative weak/self-supervised learning frameworks for detecting abnormal events. *IEEE International Joint Conference on Biometrics (IJCB)*.

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. *The Annals of Statistics*, 7(1), 1-26.

Ferryman, J., & Shahrokni, A. (2009). PETS2009: Dataset and challenge. *IEEE International Workshop on Performance Evaluation of Tracking and Surveillance (PETS-Winter)*.

Field, C. A., & Welsh, A. H. (2007). Bootstrapping clustered data. *Journal of the Royal Statistical Society: Series B (Statistical Methodology)*, 69(3), 369-390.

Hu, J., Mathur, L., Liang, P. P., & Morency, L.-P. (2025). OpenFace 3.0: A lightweight multitask system for comprehensive facial behavior analysis. *IEEE International Conference on Automatic Face and Gesture Recognition (FG)*.

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems (NeurIPS)*, 30, 3146-3154.

Kwolek, B., & Kepski, M. (2014). Human fall detection on embedded platform using depth maps and wireless accelerometer. *Computer Methods and Programs in Biomedicine*, 117(3), 489-501.

Lu, C., Shi, J., & Jia, J. (2013). Abnormal event detection at 150 FPS in MATLAB. *IEEE International Conference on Computer Vision (ICCV)*, 2720-2727.

Mittal, H., Basak, S., & Gautam, A. (2026). DIFEM: Key-points interaction based feature extraction module for violence recognition in videos. *Signal, Image and Video Processing*, 20, Article 243.

Oh, S., Hoogs, A., Perera, A., Cuntoor, N., Chen, C.-C., Lee, J. T., Mukherjee, S., Aggarwal, J. K., Lee, H., Davis, L., Swears, E., Wang, X., Ji, Q., Reddy, K., Shah, M., Vondrick, C., Pirsiavash, H., Ramanan, D., Yuen, J., … Desai, M. (2011). A large-scale benchmark dataset for event recognition in surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 3153-3160.

Pathak, G., Kumar, A., Rawat, S., & Gupta, S. (2024). Streamlining video analysis for efficient violence detection. *arXiv preprint*, arXiv:2412.02127.

Senadeera, D. C., Yang, X., Kollias, D., & Slabaugh, G. (2024). CUE-Net: Violence detection video analytics with spatial cropping, enhanced UniformerV2 and modified efficient additive attention. *IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)*.

Shao, Y., He, H., Li, S., Chen, S., Long, X., Zeng, F., Fan, Y., Zhang, M., Yan, Z., Ma, A., Wang, X., Tang, H., Wang, Y., & Li, S. (2025). EventVAD: Training-free event-aware video anomaly detection. *ACM International Conference on Multimedia (ACM MM)*.

Tran, D., Wang, H., Torresani, L., Ray, J., LeCun, Y., & Paluri, M. (2018). A closer look at spatiotemporal convolutions for action recognition. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 6450-6459.

Varma, S., & Simon, R. (2006). Bias in error estimation when using cross-validation for model selection. *BMC Bioinformatics*, 7, 91.

Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209-212.

Wu, W., Peng, H., & Yu, S. (2023). YuNet: A tiny millisecond-level face detector. *Machine Intelligence Research*, 20, 656-665.

Zhang, P., Lei, W., Zhao, X., Dong, L., & Lin, Z. (2023). RTVD-Net: A real-time violence detection method based on pre-training of human skeleton images. *12th International Conference on Networks, Communication and Computing (ICNCC)*, Osaka, Japan.

Zhang, Y., Wang, X., Ye, X., Zhang, W., Lu, J., Tan, X., Ding, E., Sun, P., & Wang, J. (2023b). ByteTrackV2: 2D and 3D multi-object tracking by associating every detection box. *arXiv preprint*, arXiv:2303.15334.

Zou, S., Tian, X., Wesemann, L., Waschkowski, F., Yang, Z., & Zhang, J. (2025). Unlocking vision-language models for video anomaly detection via fine-grained prompting. *arXiv preprint*, arXiv:2510.02155.
