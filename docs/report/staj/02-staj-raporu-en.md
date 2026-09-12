# SENTINEL — A Multi-Camera Intelligent Surveillance System

## COVER PAGE

**REPUBLIC OF TURKEY**
**DUZCE UNIVERSITY**
**FACULTY OF ENGINEERING**
**COMPUTER ENGINEERING DEPARTMENT**

**INTERNSHIP REPORT**

**Project Title:** SENTINEL — A Multi-Camera Intelligent Surveillance System
(Anomaly Detection, Emotion Analysis and Early Detection of Aggressive Behaviour)

**Student:** Ömer Faruk Kanat
**Place of Internship:** Duzce University
**Internship Supervisor:** Asst. Prof. Dr. Ahmet Albayrak
**Duration:** 25 working days (12 August – 12 September 2026)
**Repository:** https://github.com/0merf/Staj-Proje

---

## CONTENTS

1. Introduction
2. Information About the Company
3. Description of the Project and the Work to be Done
4. Project and Work Done
&nbsp;&nbsp;&nbsp;&nbsp;4.1. Technology Choices and Their Justification
&nbsp;&nbsp;&nbsp;&nbsp;4.2. System Architecture
&nbsp;&nbsp;&nbsp;&nbsp;4.3. Cascaded Processing
&nbsp;&nbsp;&nbsp;&nbsp;4.4. Datasets and the Camera Farm
&nbsp;&nbsp;&nbsp;&nbsp;4.5. Anomaly Detection
&nbsp;&nbsp;&nbsp;&nbsp;4.6. Aggression Detection
&nbsp;&nbsp;&nbsp;&nbsp;4.7. Emotion Analysis
&nbsp;&nbsp;&nbsp;&nbsp;4.8. Alert Chain and Evidence Clip
&nbsp;&nbsp;&nbsp;&nbsp;4.9. Web Interface
&nbsp;&nbsp;&nbsp;&nbsp;4.10. Security
&nbsp;&nbsp;&nbsp;&nbsp;4.11. Tests and Quality Gates
&nbsp;&nbsp;&nbsp;&nbsp;4.12. Measurement Method and Problems Encountered
&nbsp;&nbsp;&nbsp;&nbsp;4.13. Success Criteria and Results
5. Conclusion
6. Appendixes
7. Resources

---

## 1. INTRODUCTION

This report describes the 25 working days of work carried out between 12 August and 12 September 2026, as part of the internship requirement of the Computer Engineering Department of Duzce University.

The task assigned for the internship was the following: **to develop a web-based application, monitoring at least 20 cameras, on which artificial intelligence models perform anomaly detection, emotion analysis and early detection of aggressive behaviour.** The technical details were deliberately left unspecified; the choices were left to the developer. This meant that the real test of the task was not choosing a model, but **being able to justify every choice.**

When I started, I had misjudged where the difficulty of the problem lay. I assumed the central question would be "which model should I use". Within a few days it turned out that the real difficulty was elsewhere: **building an architecture capable of processing 20 concurrent video streams in real time on a single mid-range laptop graphics processor.** Model selection turned out to be a consequence of that constraint, not its cause.

A note on how this report is written. This document is not only a list of "what I did"; it also describes **why I did it and where I was wrong.** The engineering log kept throughout the project accumulated 87 entries, and in 43 of them something I believed to be true was refuted by a measurement. These entries form the most instructive part of the report; for that reason they are not hidden but treated in a section of their own (Section 4.12).

All source code, measurement scripts and measurement outputs used throughout the work are collected in a publicly accessible repository: https://github.com/0merf/Staj-Proje

The results of the project have also been turned into a journal article, prepared for submission to the *Journal of Cyber Security and Digital Economy* (CDEJ, Duzce University).

---

## 2. INFORMATION ABOUT THE COMPANY

**Name of the institution:** Duzce University
**Address:** Duzce University Konuralp Campus, 81620 Duzce, Turkey
**Field of activity:** Higher education, academic research and development
**Internship supervisor:** Asst. Prof. Dr. Ahmet Albayrak

The internship was carried out within Duzce University under the supervision of Asst. Prof. Dr. Ahmet Albayrak. The work is not a commercial product development effort but **the development of a research-grade prototype.**

This distinction has two consequences for the report. First, the measure of success is not a customer requirement but ten criteria defined in advance and expressed numerically (Section 4.13). Second, certain functions that would be mandatory in a commercial deployment (for example, face blurring under personal data protection legislation) were excluded from scope, and that decision was recorded together with its justification.

An academic discipline was adopted as the working method: at each step a single hypothesis was formed, measured with an isolated experiment, decided upon according to the result, and documented together with the reasoning behind the decision. The product of this method is a set of three document collections kept independently of the code: architecture decision records (`docs/decisions/`), the engineering log (`docs/report/problems.md`) and measurement outputs (`benchmarks/`).

---

## 3. DESCRIPTION OF THE PROJECT AND THE WORK TO BE DONE

### 3.1. Definition of the task

The task called for three capabilities, and all three had to run at the same time on the same hardware. These capabilities are summarised in Table 3.1.

**Table 3.1** The three capabilities required by the specification and the expected behaviour of each.

| Capability | What it is expected to do |
|---|---|
| Anomaly detection | Learn what is "normal" for each camera and report deviations from that normal |
| Emotion analysis | Classify the facial expressions of the people in the image |
| Early detection of aggressive behaviour | Notice a violent incident, ideally before it begins |

In addition, the system had to be web-based, had to monitor at least 20 cameras concurrently, and had to run in real time.

### 3.2. Working environment and constraints

The constraints were clear from the start and determined every architectural decision. Table 3.2 shows these constraints and how each was reflected in the architecture.

**Table 3.2** Hardware, data and time constraints of the project and their consequences for the architecture.

| Constraint | Value | Consequence |
|---|---|---|
| Graphics processor | RTX 3070 Laptop, 8 GB | Models must be loaded as a single copy |
| Processor | 20 logical cores | Pre-processing and inference share the same cores |
| System memory | 16 GB | A limit on a multi-process architecture |
| Real IP camera | **None** | 20 cameras to be simulated from video files |
| Duration | 25 working days | Scope must be kept tight |
| Developer | 1 person | No work can be done in parallel |

It should also be noted from the outset that a laptop graphics processor delivers roughly 65 to 75 percent of the performance of the desktop model carrying the same name, and is subject to thermal throttling. In other words, the hardware available was a budget below even "mid-range".

### 3.3. Success criteria

Before the work began, ten success criteria were defined numerically. The reason is simple: **a criterion defined afterwards takes its shape from the result obtained.** The criteria and their targets are given in Table 4.10.

In the words of the project plan itself: *"Failing to meet a target is not failure; failing to measure is."* This sentence also sets the tone for the rest of the report.

---

## 4. PROJECT AND WORK DONE

### 4.1. Technology Choices and Their Justification

Every technology choice was recorded together with a justification. The main choices and the reasons for them are summarised in Table 4.1.

**Table 4.1** Technology choices and their justification.

| Layer | Choice | Justification |
|---|---|---|
| Language and back end | Python 3.13 + FastAPI | The AI ecosystem is in Python. ASP.NET Core was evaluated and eliminated |
| Message queue | Valkey 8 | A BSD-licensed fork of Redis; the same client library works |
| Database | PostgreSQL 17 + TimescaleDB | Event records are a time series; continuous aggregation was needed |
| Media server | MediaMTX | Produces the simulated cameras and serves WebRTC without re-encoding |
| Video decoding | PyAV | Used as a library, never shelling out: no command injection surface |
| Object detection | YOLO26-s | An architecture that requires no NMS, suited to the real-time target |
| Tracking | BoT-SORT (Aharon et al., 2022) | A separate instance per camera; CMC disabled since cameras are static |
| Pose estimation | YOLO26-pose | Top-down: the detection box is cropped and fed to the model |
| Face and expression | YuNet (Wu et al., 2023) + EmotiEffLib | Lightweight; expression classification carries a low fusion weight |
| Front end | React 19 + TypeScript + Vite | Canvas control was required for live box drawing |
| Reverse proxy | Caddy | Automatic TLS and `forward_auth` support |
| Observability | Prometheus + Grafana | The measurement infrastructure became the backbone of the project |

Some of these choices **changed** during the project, and those changes were recorded with their justifications as well. For example, Garage had been chosen as the object store; since a single-machine deployment does not have the problem an object store solves (distributed storage), it was removed from scope and clips were written to local disk instead.

### 4.2. System Architecture

The system consists of five independent processes, and communication between them is carried over Valkey streams. Figure 4.1 shows this flow together with the measured cost of each step.

**[GORSEL: diagrams/01-veri-akisi.png]**
**Figure 4.1** Data flow of the system and the measured costs. The numbers on the boxes are not estimates but measurement results.

Four rules were adopted in the architecture, and all four derive directly from the hardware constraint.

**Raw video frames do not pass through the message queue.** A 1080p frame is roughly 6 MB. Writing that volume of data into a queue from twenty cameras at a few frames per second turns the queue itself into the bottleneck. Instead, frames are written to **shared memory** and only a reference travels through the queue. The pool consists of 96 slots, each holding one complete 720p frame (1280 × 720 × 3 bytes = 2.76 MB), 265 MB in total.

The pool being this small is not a storage decision but a **queueing decision.** The slots hold only those frames in flight between ingest and inference. Beyond a certain point, enlarging the pool brings no benefit: if the consumer is saturated, a larger buffer does not increase throughput, it merely causes the frames waiting in the queue to be older, and therefore increases latency.

**The server does not draw boxes onto the video.** Video travels to the browser directly from the media server over the WebRTC-based WHEP protocol; detection boxes travel as JSON over a separate WebSocket connection and are drawn by the browser. Thanks to this separation, there is no need to re-encode 20 separate video streams on the server.

**Models are in a single process, in a single copy.** The measured video memory usage is 571 MB, that is, 7 percent of 8 GB.

**Every queue is bounded.** An unbounded queue means memory exhaustion whenever the producer is faster than the consumer. Old frames are dropped rather than held, and the number of dropped frames is measured separately.

### 4.3. Cascaded Processing

Processing twenty streams on a single graphics processor is possible only because not every model is applied to every frame. The stages and their costs are shown in Figure 4.2.

**[GORSEL: diagrams/02-kademeli-isleme.png]**
**Figure 4.2** Cascaded processing and the measured cost of each stage. The bars on the right are in milliseconds per frame.

- **Stage 0, motion gate (on the processor).** Static scenes are eliminated by comparing consecutive frames. There is also adaptive sampling: on a camera where no motion has been seen for a long time, the sampling rate falls from 4 frames per second to 1.
- **Stage 1, object detection (on the graphics processor).** Only the person class is sought.
- **Stage 1b, tracking.** A separate tracker instance is kept for each camera; because tracking state is held within the camera, a given camera must always be routed to the same process.
- **Stage 2a, pose estimation.** Applied to every detected person box. The most expensive item in the loop: 10.96 ms per frame, 48 percent of the budget.
- **Stage 2b, face and expression.** Thinned out by a two-step gate (Section 4.7).

There is one stage that was planned but **not implemented**: Stage 3, the video-based action verifier. It was foreseen that when the escalation score crossed a threshold, a short video segment would be fed to a three-dimensional convolutional network to confirm or reject the alert. The reason it was not implemented is explained in Section 5. A stage that appears in the documentation but not in the code is a false statement; it has therefore not been passed over silently but written out explicitly.

### 4.4. Datasets and the Camera Farm

Because no real IP cameras were available, the 20 cameras were simulated by broadcasting video files compiled from different datasets in an **infinite loop** through a media server. From the system's point of view these streams are indistinguishable from real RTSP cameras. The source datasets used and the cameras each feeds are given in Table 4.2.

**Table 4.2** Source datasets of the camera farm.

| Dataset | Cameras | Content | Purpose of use |
|---|---|---|---|
| VIRAT Ground 2.0 (Oh et al., 2011) | cam-01 – cam-08 | Static surveillance: car park, campus, building entrance | Letting the anomaly module learn a "normal" |
| Oxford Town Centre (Benfold and Reid, 2011) | cam-09 | Dense pedestrian traffic, with ground truth | Tracking accuracy reference |
| PETS 2009 (Ferryman and Shahrokni, 2009) | cam-10 – cam-14 | Multi-camera crowds, sudden dispersal | Crowd and dispersal rules |
| UBI-Fights (Degardin and Proença, 2020) | cam-15 | Long-duration surveillance containing violent incidents | Early warning, measurement with context |
| UR Fall Detection (Kwolek and Kepski, 2014) | cam-16 | Controlled fall recordings | Validation of the fall rule |
| RWF-2000 (Cheng et al., 2021) | cam-17 | Fight clips sourced from surveillance | Aggression module |
| CUHK Avenue (Lu et al., 2013) | cam-18, cam-19 | Campus surveillance, frame-level labels | Anomaly control and testing |
| Pexels | cam-20 | Scenes containing close-up faces | Testing of the expression module |

In addition, the laptop's own camera was connected to the system as "cam-21, live", in order to show during the demonstration that the system also works with a real camera.

**The effect of looping on the measurements.** The durations of the source videos range from 5 seconds to 345 seconds. A single fall incident in the shortest source replays roughly 720 times per hour and produces an alert on every pass. This makes raw rates of the "alerts per camera-hour" kind unusable: the same system, the same algorithm and the same incident produce 720 alerts per hour with a 5-second source and 12 with a 300-second one. The raw rate measures not the behaviour of the system but the length distribution of the test videos. This finding led to a change in the definition of the criterion (Section 4.13).

### 4.5. Anomaly Detection

Anomaly detection consists of two layers and a combination stage.

**Layer A, learned normal.** A separate profile is kept for each camera. The profile consists of the position distribution, the speed distribution and the density distribution of the people on that camera. The further an observation deviates from this profile, the higher the anomaly score. The architectural rule is explicit: **the normal of each camera is learned separately.** Running in a corridor is an anomaly; running in a gym is not.

**Layer B, physical rules.** Events such as falls, running, loitering and crowding are sought with rules derived from pose and tracking data. The fall rule, for example, looks at the aspect ratio of the torso, the inclination of the torso and the rate of change of that inclination.

**Fusion.** For each tracked person, five signals are produced in the 0 to 1 range and summed with the weights in Table 4.3.

**Table 4.3** The five signals combined by the fusion layer and their weights. The weights sum to 1.00.

| Signal | Weight |
|---|---|
| Aggression | 0.40 |
| Profile deviation (Layer A) | 0.25 |
| Physical rule violation (Layer B) | 0.20 |
| Facial expression | 0.10 |
| Crowd density | 0.05 |

The total score is then smoothed temporally with an **exponential moving average**, and hysteresis is applied. Smoothing means that instead of using the score computed in consecutive windows directly, it is blended with the previous value; the aim is to prevent a single noisy window from raising an alert.

**A measurement result and a refuted claim.** Anomaly detection was measured on the CUHK Avenue dataset (9 clips, 1439 frames). The area under the curve for fusion is **0.869**, with a cluster bootstrap (Efron, 1979; Field and Welsh, 2007) 95 percent confidence interval of [0.806 – 0.929].

However, to test the claim that "fusion helps", a **control series** was defined: the *same* smoothing used in fusion was applied to a single signal. The results are given in Table 4.4.

**Table 4.4** Control series: the contributions of smoothing and of signal combination were measured separately (CUHK Avenue, 9 clips, 1439 frames).

| Signal | AUC |
|---|---|
| Profile deviation, raw | 0.789 |
| Profile deviation + smoothing (control) | 0.860 |
| Fusion (5 signals + smoothing) | 0.869 |

Smoothing gains 0.071 points; combining five signals adds 0.009. The significance threshold had been set at 0.02 **before** the measurement; the difference falls below that threshold. In other words, on this dataset what produces the gain is not signal combination but temporal smoothing.

This does not mean that fusion is unnecessary. On this dataset two of the five signals are inoperative: the AUC of the physical rule signal is exactly 0.500, meaning that it never fires (the anomalies in Avenue are bag throwing, bicycles and wrong-way movement; our rules are defined on human motion). The aggression signal, at 0.457, is below chance level. **Combining inoperative signals cannot gain anything.** The measured contribution of fusion lies not in discriminative power but in noise suppression.

### 4.6. Aggression Detection

Three approaches to aggression detection were developed and measured in sequence.

**First: rule-based.** Wrist speed, torso inclination, motion energy and inter-person proximity were derived from the joint positions produced by pose estimation, and these were combined with manually chosen weights. On a subset of 120 clips this gave an AUC of 0.62 to 0.66 and an F1 of roughly 0.71.

Why this approach remained limited was investigated separately, and the result was instructive: the weights rested on the assumption that violence involves **fast and sudden** movement. The measurement did not support that assumption. A substantial proportion of the real violent incidents in the dataset take the form of **grappling**, and the motion speed measured during grappling can come out lower than that of normal walking within a crowd. The hand-written weights were encoding an unmeasured intuition.

**Second: skeleton features + a gradient boosting model (LightGBM, Ke et al., 2017).** The features are the same; the only thing that changes is how they are combined.

**Third: raw pixels + a three-dimensional convolutional network (R3D-18, Tran et al., 2018).** This approach does not depend on skeleton extraction at all, and therefore also works in cases where pose estimation fails.

The results of the last two models and of their combination are given in Table 4.5.

**Table 4.5** Violence detection results (RWF-2000 validation set, 96 clips).

| Model | AUC | AUC 95% CI | F1 |
|---|---|---|---|
| Skeleton + LightGBM | 0.9267 | 0.8676 – 0.9722 | 0.8889 |
| Raw pixels (R3D-18) | 0.9366 | 0.8820 – 0.9796 | 0.9107 |
| **Combination (average)** | **0.9684** | **0.9352 – 0.9917** | **0.9369** |

**The mechanism behind the gain.** That the combination gives a better result is not in itself an explanation; it must be shown *why* the two models complement each other. The error sets were compared: 10 clips on which only the skeleton model is wrong, 9 clips on which only the video model is wrong, and **1 clip on which both are wrong.** The overlap is 10 percent. The models make their errors on different clips, not the same ones; this is where the gain comes from.

**Threshold selection bias.** The F1 values are obtained by searching for the best threshold on the same set on which F1 is computed, and are therefore optimistic. The optimism measured with 400 repeated stratified half-splits is 0.0204 points for the combination: that is, **0.9165** rather than 0.9369. Both values are reported.

**Early warning, and the ceiling of the criterion.** The criterion required a warning at least 2 seconds before violence begins. The measurement came out negative: the median lead is **−1.10 seconds**, meaning the warning arrives after the incident.

The real finding, however, is not that number. The **highest value the criterion can reach** on this dataset was computed: the median duration of context before the onset of violence in the clips is 0.58 seconds, and the maximum is 3.07 seconds. In only 2 of the 20 clips is a 2-second lead physically possible. Furthermore, I marked the labels myself, and the marking contains my own reaction time; watching the clips shows that violence actually begins within the 0 to 0.5 second range. **Even a perfectly functioning detector could not satisfy this criterion.**

The finding was also tested on a second dataset with different characteristics. On a clip containing 58 seconds of context before the incident, the model can distinguish the moment of the fight from normal (median score ratio 2.756), but the **escalation** window leading up to the fight is scored lower than the normal sections (0.184 against 0.282), and detection occurs 1.76 seconds after the incident. Two datasets arrive at the same conclusion by different routes: the system detects violence, but it does not distinguish the escalation that precedes violence.

### 4.7. Emotion Analysis

Facial expression classification is thinned out by a two-step gate: first the height of the person box must exceed 180 pixels, then face detection must succeed.

The measurement made over 21 cameras and 25 frames per camera is given in Table 4.6.

**Table 4.6** Numbers of people and faces passing the two-step gate of the expression stage (21 cameras, 25 frames per camera).

| Step | Result |
|---|---|
| 1. Person box ≥ 180 pixels | **171** of 2087 people passed (8.2%) |
| 2. Could a face be detected | **No face at all** was found on 7 of the 8 cameras that passed the gate |

A face can be found only on the camera containing close-up shots (cam-20), and there in all 25 of the 25 crops.

This result has two meanings. First, the fact that the expression stage is cheap (0.46 ms per frame, 2 percent of the loop) is not an efficiency achievement; it is **the consequence of the gate eliminating almost everything.** Second, and more importantly, the expression signal is in practice produced on a single camera. Because fusion treats a missing signal as zero, the expression weight is effectively disabled on the other cameras.

This does not mean the expression model is poor; it means that **faces in surveillance footage are not large enough to pass the gate.** That the gate is passed completely on the close-up camera supports this interpretation.

The most instructive incident concerning this module over the course of the project was the following: the expression signal was visible on screen but **never entered the decision.** The code claimed the opposite. Once the signal was connected to fusion, it began contributing to the decision for the first time. Furthermore, at one point the ONNX runtime had become corrupted and the stage could not be constructed at all; because a label still appeared on screen, the problem went unnoticed for a long time.

### 4.8. Alert Chain and Evidence Clip

The alert chain works as follows: when the fusion score crosses a threshold and the cooldown period has elapsed, an event is produced, and that event goes to three places at once. It is written to the database for permanent storage, an evidence clip is cut, and it is sent live to the dashboard over a WebSocket.

Events are written to TimescaleDB, using a hypertable and a retention policy. The dashboard loads the last 24 hours of history on start-up, so that alerts produced while the dashboard was closed can also be seen.

**Evidence clip.** When an alert is produced, ±10 seconds around the moment of the event is cut from the source recording, stored, and made playable in the dashboard. The cut is performed without re-encoding (remux), at a cost of roughly 32 ms. Verification that a cut clip really contains the incident is shown in Figure 6.3.

Two lessons emerged from this chain. First: for a long period, clips were being cut and written to the database but **were not accessible in the dashboard**, that is, the chain was complete on paper and half-finished in practice. Second: the clip-cutting script was reporting success as "12/12 clips cut", when in fact the files produced were 257 bytes long, contained no frames at all, and could not be opened. The success check had been written as "the file exists and its size is greater than zero". The check was changed so that it does the job the file is supposed to do: the file is actually opened and its first frame is read.

### 4.9. Web Interface

The interface was developed with React 19 + TypeScript + Vite. It consists of three pages: the camera grid (Figure 4.3), the event timeline (Figure 4.4) and the camera detail page. The login screen is shown in Figure 6.1 and the initial state of the grid in Figure 6.2.

**[GORSEL: screenshots/03-canli-kutular.png]**
**Figure 4.3** The camera grid: detection boxes, track identifiers, confidence scores and skeletons drawn over live video. The panel on the right shows alerts and the evidence fields of each alert.

**Aligning the boxes with the video.** This was the hardest part of the interface. The analysis result arrives a few hundred milliseconds after the video frame; where should the box be drawn?

The first approach was to **predict** where the person is now from the velocity vector (extrapolation). People slow down, turn and stop; the prediction does not hold, and the next real result snaps the box to the correct place. The "stuttering" reported by the user was exactly this.

The established solution in the multiplayer game networking literature says the opposite: **do not predict, delay the image.** If the video is made to lag by as much as the analysis does, then for the moment being displayed on screen there are two real measurements available, and the position in between is interpolated. The browser has a ready-made control for this: `jitterBufferTarget`. The price is freshness, which is acceptable in surveillance, because for the operator having the box in the right place matters more than the image being half a second fresher, and the alert already arrives without delay over a separate channel.

**[GORSEL: screenshots/05-zaman-cizelgesi.png]**
**Figure 4.4** The event timeline and the event table. In the heat map above, the rows are cameras and the columns are hours; clicking a cell narrows the table below to that camera and that hour.

In its first version, the timeline was only a heat map and the cells were not clickable. Information was being produced but was not reaching the user. The cells were turned into buttons and a real event table was added beneath them, showing time, camera, type, person, severity, evidence strength and evidence fields. Clicking a row opens all evidence fields and, where one exists, the evidence clip.

A light/dark theme option was also added to the interface. Colours are defined as CSS variables; the preference is stored in the browser and applied before React loads, so that there is no theme flash on start-up.

### 4.10. Security

Security requirements were defined at the start of the project as a prioritised list of 20 items and tracked throughout development. The structure of the single entry point and of video stream authentication is shown in Figure 4.5. Among the items implemented are password storage with Argon2id, short-lived JWT tokens, an `HttpOnly` cookie, three-role authorisation (viewer/operator/administrator), a login rate limit, an append-only audit log, path traversal protection and TLS.

**[GORSEL: diagrams/03-kimlik-dogrulama.png]**
**Figure 4.5** The single entry point and authentication of the video stream.

On the security side, two findings taught the same lesson twice.

**First finding: the API was protected but the video was not.** The application interface required authentication; the media server serving the video stream performed no verification at all. All that was needed to access the footage was knowing the address. The first fix was a network restriction: the port was bound to the local interface. This does not close the hole; it merely limits access to the same machine. The permanent solution was to serve the video from the **same origin** as the application and have the reverse proxy ask the application for authorisation on every video request. In this design the browser attaches the identity cookie to video requests as well; that is, the single entry point is not a convenience but a precondition for video authentication.

**Second finding: a single entry point was built, but what passed through it was never counted.** The "pass everything else through" rule in the reverse proxy was also exposing those application endpoints that have no authentication. During the audit it was observed that the observability interface (`/metrics`) was accessible without authentication and through the single entry point. That interface contains camera names, per-camera alert counts, frame rates and an endpoint inventory; in a surveillance system this is enough to perform reconnaissance without entering the system at all. The endpoint was closed at the reverse proxy level.

Adding authentication at the application level was not chosen, because the metrics collection process uses this interface locally and without passing through the proxy; protection at the application level would have broken observability. **The right layer is the layer that faces outward.**

One further thing was observed during the audit and is worth noting: the first tool used to produce the inventory walked the object graph of the application framework and found 10 endpoints. Endpoints added through sub-routers were invisible to that walk; the real number is 16. The tool could not see part of the surface, and did not say so. The method was changed: real unauthenticated requests were sent to **all** endpoints taken from the interface definition, and the returned status codes were recorded. The tool that produces the inventory must itself be verified.

**Third finding: the configuration was producing false statements.** Of 69 settings, 11 were not read on any code path. Two of them amounted directly to security claims: one suggested that signed, time-limited clip links were configured, and the other that request rate limiting was in place across the whole API. In reality the signed-link feature was never implemented, and rate limiting exists only on the login endpoint. This is not a code defect, since no function is broken, but anyone examining the configuration would conclude that protections exist which the system does not have. The settings were marked with an explicit note that they are not implemented.

### 4.11. Tests and Quality Gates

The project has three test layers; the layers, test counts and what each layer verifies are summarised in Table 4.7.

**Table 4.7** The three test layers of the project, test counts and what each layer verifies.

| Layer | Count | What it verifies |
|---|---|---|
| Back-end unit tests | 229 | Logic that runs without requiring infrastructure |
| Front-end unit tests | 44 | Timeline mathematics, box drawing, type dictionary |
| End-to-end tests (Playwright) | 22 | Against the live system, the jobs a user can do |

Quality gates: `ruff` (formatting and errors), `mypy` (type checking), `eslint` and `tsc`. All four are clean.

**Why end-to-end tests were needed.** Three times during the project the following happened: a system whose every part worked individually did not work end to end, and the part tests did not show it. The expression signal was being classified and sent to the screen but was not entering the decision. The memory pruning function of fusion had been written but was never called. Clips were being cut and written to the database but were not accessible. All three would have passed the unit tests.

For that reason the names of the end-to-end tests describe **jobs**, not modules: "the operator can click an event and see its evidence", "an unauthenticated video request is blocked", "video actually arrives on every camera that is opened".

**A test passing is not enough.** A unit test written during the project claimed "I catch the old defect"; when measured, it turned out that it did not. From that day on, newly written tests were not accepted **until the code had been deliberately broken and the test had been seen to fail.** The same rule was applied to the diagram verification test: the test said "overflow check" but only looked at the edge of the page, and could not see a real overflow (a label ending up underneath another box). The test was fixed, and then deliberately broken to confirm that it failed.

### 4.12. Measurement Method and Problems Encountered

This section is the part of the project that taught the most. The engineering log kept throughout the project contains 87 entries. Not all of them are scientific findings; classified, they break down as shown in Table 4.8.

**Table 4.8** Distribution of the 87 entries in the engineering log by type.

| Group | Count | Content |
|---|---|---|
| Entries where a claim was **refuted** by measurement | 43 | The real material of the report |
| Findings at the architectural or implementation level | 35 | Queueing, memory, concurrency |
| Setup and environment problems | 9 | Port conflicts, tool configuration |

Calling the last group "findings" would not be accurate; that is why it was separated out.

What the 43 entries in the first group have in common is this: **the error was not in the model or in the system, but in the measurement chain.** The most frequently recurring error types and the measures taken are collected in Table 4.9.

**Table 4.9** Types of measurement error encountered and their corrections.

| Type of error | Symptom | Correction |
|---|---|---|
| Reading a percentile from a cumulative counter | Different results under the same conditions | Taking window differences |
| Confusing wall-clock time with processor time | Cost appearing lower than it is | Measuring with `thread_time` |
| Two different units under the same metric | Component sum not matching the loop total | A single unit + a closure check |
| Treating the unmeasured as zero | Unexplained cost remaining invisible | Closure check |
| Mistaking the tool's ceiling for the system | Round values that arouse no suspicion | Control series |
| Treating dependent observations as independent | Confidence intervals coming out narrow | Cluster bootstrap |
| Choosing the threshold on the measurement set | Optimistic F1 | Repeated half-splits |

A few concrete examples follow.

**The false diagnosis of "decoding is the bottleneck".** Early on it was assumed that video decoding was the bottleneck, and hardware-accelerated decoding (NVDEC) was tried. When measured, NVDEC turned out to be **slower** than the processor, and decoding turned out not to be the bottleneck in the first place. It was later measured that only 5.6 percent of the ingest worker's CPU time goes to decoding.

**There was no such thing as the "unmeasured 70 percent".** At one stage it was reported that 70 percent of the pipeline cost was unmeasured overhead, and architectural proposals were built on top of that. The error was summing two different units under the same metric: some stages were writing per frame and others per batch. When a **closure check** was added, that is, when the sum of the components was compared against an independently measured loop total, the gap turned out to be 0 percent. The measurement was repeated a day later with a different tool and gave the same result.

**Increasing the input reduced the output.** When the sampling rate was raised from 4 to 8 frames per second per camera, the analysed frame rate did not increase but **fell by 32 percent** (2.78 to 1.88). The mechanism was visible in the measurement: the processor usage of the ingest process rose from 2.10 to 3.79 cores, while that of the inference process stayed constant. The increased ingest load was stealing time from the inference process sharing the same cores.

**A measurement whose artefact was not saved has not been made.** When the shared memory pool was raised from 48 to 96 slots, a clear improvement was observed and written into the log, but the measurement output was not saved to a file. Measurements made the following day with the same configuration did not reproduce those values. For this reason, the report and the article are based on measurements that are reproducible and whose outputs are stored.

**The parallelisation experiment.** Because the inference process saturates on a single core, distributing the cameras across several processes was attempted. The first implementation **destroyed half the frames**: processes reading the same stream were discarding frames that did not belong to them instead of handing them to the other process. Worse, the metrics appeared to have *improved*, because halving the work emptied the queue and reduced latency. An evaluation that looked only at latency would have taken this for a success. The error was seen only because the numbers of published and analysed frames were counted separately.

In the corrected implementation, routing was moved to the producer side and each camera was written to its own sub-stream. The result: throughput rose by 19 percent and latency fell by 49 percent. But system memory went from 84 percent to **98 percent**; on a 16 GB machine that margin is not safe for long-running operation. For that reason the option was not enabled in production.

### 4.13. Success Criteria and Results

**Table 4.10** Success criteria and measured values.

| # | Criterion | Target | Measured | Status |
|---|---|---|---|---|
| K1 | Concurrent cameras | ≥ 20 | 20 / 20 | Met |
| K2 | Analysis frame rate (per camera) | ≥ 4 fps | 2.34 | Not met, cause measured |
| K3 | End-to-end latency | ≤ 1500 ms | p50 378 ms, p95 652 ms | Met |
| K4 | Two hours without interruption | No interruption | 120 min, 0 interruptions | Met (earlier version) |
| K5 | Violence detection F1 | ≥ 0.85 | 0.937 (bias-corrected 0.917) | Met |
| K6 | Anomaly detection AUC | ≥ 0.75 | 0.869 (cluster CI 0.806 – 0.929) | Met |
| K7 | False alerts | ≤ 3 per camera-hour | Precision 0.895 (19 independent events) | Criterion redefined |
| K8 | Early warning lead | ≥ 2 s | −1.10 s | Not met, criterion ceiling below target |
| K9 | Security priority list | 100% | 18 / 19 | Partial |
| K10 | Interface smoothness | ≥ 30 fps | Median 30.00 | Criterion not discriminative |

**Resource usage.** The memory and processor values measured per process while the system runs in steady state with 20 cameras are given in Table 4.11.

**Table 4.11** Memory and processor usage measured per process in steady state with twenty cameras.

| Component | Memory (MB) | Processor (cores) |
|---|---|---|
| Ingest | 1295.0 | 2.42 |
| Inference | 1077.2 | 0.89 |
| Analytics | 133.5 | 0.93 |
| Alerting | 57.9 | 0.00 |
| API | 74.1 | 0.02 |
| **Total** | **2633.9** | **4.27** |

Graphics processor usage is at a median of 28.5 percent, and video memory usage is 571 MB (7 percent of 8192 MB).

**Why K2 was not met.** While the system falls short of the target, roughly 15 of the 20 logical cores, roughly 70 percent of the graphics processor and 93 percent of the video memory go unused. The limiting factor is not the hardware but **the serial nature of the main loop of the inference process.** The loop processes a batch from start to finish, using a single core while doing so; the measured value is 0.89 cores, and it does not rise above this regardless of load. Waiting time was measured separately at 1.69 ms per frame. In other words the process is not sitting idle; it is doing work 93 percent of the time.

**Why K7 was redefined.** The "alerts per camera-hour" criterion does not measure the behaviour of the system in a setup where source videos are broadcast in a loop (Section 4.4). The criterion was redefined as precision per independent event. Of 40 alerts, 39 were labelled by hand (one could not be decided and was excluded from the analysis), and when deduplicated by position within the loop these corresponded to 19 independent events. The results are given in Table 4.12.

**Table 4.12** Alert precision. Confidence intervals were computed with the method of Wilson (1927).

| | n | Correct | Precision | 95% CI |
|---|---|---|---|---|
| Raw labelled alerts | 39 | 37 | 0.949 | 0.831 – 0.986 |
| **Independent events** | **19** | **17** | **0.895** | **0.686 – 0.971** |
| Crowd | 9 | 9 | 1.00 | 0.70 – 1.00 |
| Combined risk | 5 | 5 | 1.00 | 0.57 – 1.00 |
| **Fall** | **5** | **3** | **0.60** | **0.23 – 0.88** |

The aggregate value is 0.895, but the distribution by type is not uniform: both of the two false alerts are of the fall type and both arise from the same mechanism, a person bending down and lying on the floor being taken for a fall. An aggregate number can conceal a finding; had only 0.895 been reported, it would not have been visible that the weak link of the system is one particular rule.

One limitation must be stated explicitly here. This method measures **precision** only. **Recall was not measured**; determining the events the system misses would have required labelling the entirety of the source videos.

**Why K10 is not discriminative.** Interface smoothness was measured across 7 independent runs. The drawing rate has a median of 30.00 (range 29.43 – 30.02), while the control measurement taken without any camera opened is around 60. The drawing-rate measurement depends on the browser's vertical synchronisation, and on a 60 Hz display it takes **discrete** values in practice, such as 60, 30, 20 and 15. The threshold of the criterion is exactly 30, that is, at the very step on which the system sits; whether the measured value comes out as 29.43 or 30.02 is determined not by the success of the system but by the edge effects of the counting window.

More informative is the dropped-frame rate: a median of 2.3 percent, with a range of 0 to 33.4 percent. In an early measurement this rate was found to be zero and was interpreted as "better than I expected"; the distribution over 7 runs invalidated that interpretation. **A result resting on a single observation, particularly when it comes out better than expected, should not be accepted without repetition.**

---

## 5. CONCLUSION

At the end of 25 working days, a system was delivered in working condition that processes 20 concurrent camera streams on a single mid-range laptop graphics processor, combines the detection-tracking-pose-face chain with anomaly detection and aggression estimation, stores events permanently, and can be monitored live through a web interface.

**Targets that were met.** End-to-end latency stayed well below the target (p50 378 ms against a target of 1500 ms). In violence detection, the combination of two independent models gave an F1 of 0.937 (bias-corrected 0.917), and **why** this gain arises was also shown: the error sets of the two models overlap by only 10 percent. Anomaly detection exceeded its target with an AUC of 0.869. All 20 cameras ran concurrently.

**Targets that were not met, and their causes.** Three criteria failed to reach their targets, and the cause of each was measured:

- **Analysis frame rate (K2).** The limit is not the hardware but the serial nature of the inference loop. There is clear headroom in the hardware: the graphics processor at 28.5 percent, video memory at 7 percent, most cores idle.
- **Early warning (K8).** On the dataset used, the highest value the criterion can reach is below the target. Even a perfect detector could not pass it. This is not a system failure but a mismatch between criterion and data.
- **Interface smoothness (K10).** The threshold of the criterion falls above the resolution step of the measurement tool; the verdict changes with measurement noise.

**What was excluded from scope.** Stage 3 (the video-based action verifier) was not implemented. The model was in fact trained and used in violence detection, but connecting it to the live pipeline as a verification stage would require trigger logic, segment buffering and an alert-retraction flow. Furthermore, the measurements showed that alert precision is already 0.895 and that the false alerts are concentrated in a single rule type; in that case a targeted correction is more productive than a general verification stage. Per-camera authorisation was likewise excluded from scope, as it has no counterpart in a single-operator deployment.

**What I learned in this internship.** Beyond technical knowledge, I learned three things, and all three concern measurement.

First: **the measurement tool is a component too, and it can also be broken.** In most of the 43 entries in which a claim was refuted by measurement in this project, the error was not in the model but in the measurement chain. Reading a percentile from a cumulative counter, confusing wall-clock time with processor time, summing two different units under the same metric: none of these concern the model, yet all of them change the result.

Second: **a criterion must itself be audited before it is reported.** Three questions suffice. What is the highest value this criterion can reach with the data at hand? Is its threshold above the resolution of the measurement tool? Is the observation unit genuinely independent? When these three questions are not asked, the number obtained may not be wrong, but it may be answering the wrong question.

Third: **a system whose every part works individually may not work end to end, and part tests will not show it.** Scope items should be marked off not with modules but with the jobs a user can do. "Clips are being cut" is a module statement; "the operator can watch the video of an alert" is a scope statement.

**Future work.** Three directions stand out. First, using a dataset that **contains pre-incident context**, so that the early warning criterion can be evaluated meaningfully; it was shown by measurement that neither of the two datasets used in this work has that property. Second, having the labelling performed by multiple annotators and reporting inter-annotator agreement. Third, validating the system under real network conditions and with real cameras.

---

## 6. APPENDIXES

**Appendix A — Additional screen outputs.**

**[GORSEL: screenshots/01-giris.png]**
**Figure 6.1** The login screen. The whole dashboard sits behind authentication; an unauthenticated request is redirected straight to this page. Passwords are stored with Argon2id, and the session is carried by a short-lived JWT token in an `HttpOnly` cookie.

**[GORSEL: screenshots/02-izgara-20-kamera.png]**
**Figure 6.2** The initial state of the camera grid. Twenty tiles are listed, but the video stream does not start automatically on any of them; each tile reads "click to watch". The reason is the browser-side decoding cost described in Section 4.9: opening twenty H.264 streams at once saturates the browser, so streams are started on demand. The alert panel on the right, however, keeps working while the tiles are closed, because alerts arrive over a channel independent of the video.

**[GORSEL: screenshots/07-klip-zinciri-dogrulama.png]**
**Figure 6.3** Verification of the evidence clip chain. Six consecutive frames taken from the clip cut for a fall alert, read left to right and top to bottom. The clip contains the correct moment: the person is standing, walks, loses balance and falls to the floor. This verification was done by hand, because what must be checked is not that the file opens but that it genuinely contains the incident (Section 4.8).

**Appendix B — Repository structure.** Source code, measurement scripts and measurement outputs: https://github.com/0merf/Staj-Proje

```
backend/          Python: ingest, inference, analytics, alerting, API
  src/sentinel/   Application code
  scripts/        Measurement and evaluation scripts
  tests/          229 unit tests
frontend/         React + TypeScript dashboard
  src/            Application
  e2e/            22 end-to-end tests (Playwright)
infra/            Docker, Caddy, MediaMTX, Prometheus configurations
benchmarks/       Measurement outputs (JSON), reproducible
docs/
  decisions/      Architecture decision records
  report/         This report, the journal article, diagrams, screenshots
    problems.md   Engineering log (87 entries)
```

**Appendix C — Installation and running.**

```
docker compose up -d                      # infrastructure
pwsh backend/scripts/start_all.ps1        # AI processes
# Dashboard: http://127.0.0.1:8001/app
```

**Appendix D — Measurement scripts.** Every number appearing in the report can be reproduced with the scripts in Table 6.1.

**Table 6.1** Measurement scripts that reproduce the numbers given in the report.

| Script | What it measures |
|---|---|
| `measure_canli.py` | End-to-end latency, analysis frame rate, resource usage |
| `asama_kirilimi.py` | Stage breakdown of the inference loop and the closure check |
| `evaluate_k6.py` | Anomaly detection AUC and the control series |
| `evaluate_birlesim.py` | Violence detection, combination, bootstrap, threshold bias |
| `evaluate_k8.py` | Early warning lead and the criterion ceiling |
| `alarm_tekillestir.py` | Alert precision (with loop deduplication) |
| `benchmark_tensorrt.py` | PyTorch versus TensorRT comparison |

**Appendix E — Location of the source code.** In order not to exceed the page limit of the report, the source code has not been embedded in this document but left in the repository. The file paths of the main components are given in Table 6.2.

**Table 6.2** File paths of the main components within the repository.

| Component | File |
|---|---|
| Ingest worker | `backend/src/sentinel/ingest/worker.py` |
| Inference worker | `backend/src/sentinel/inference/worker.py` |
| Analytics and fusion | `backend/src/sentinel/analytics/` |
| Alert engine and clips | `backend/src/sentinel/alerting/` |
| Shared memory | `backend/src/sentinel/bus/shm.py` |
| Dashboard | `frontend/src/` |

---

## 7. RESOURCES

Aharon, N., Orfaig, R., Bobrovsky, B.Z., *BoT-SORT: Robust Associations Multi-Pedestrian Tracking*, arXiv:2206.14651, 2022.

Benfold, B., Reid, I., "Stable Multi-Target Tracking in Real-Time Surveillance Video," *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, June 2011, pp. 3457-3464.

Cheng, M., Cai, K., Li, M., *RWF-2000: An Open Large Scale Video Database for Violence Detection*, 25th International Conference on Pattern Recognition (ICPR), January 2021, pp. 4183-4190.

Degardin, B., Proença, H., *Human Activity Analysis: Iterative Weak/Self-Supervised Learning Frameworks for Detecting Abnormal Events*, IEEE International Joint Conference on Biometrics (IJCB), September 2020.

Efron, B., "Bootstrap Methods: Another Look at the Jackknife," *The Annals of Statistics*, January 1979, pp. 1-26.

Ferryman, J., Shahrokni, A., *PETS2009: Dataset and Challenge*, IEEE International Workshop on Performance Evaluation of Tracking and Surveillance, December 2009.

Field, C.A., Welsh, A.H., "Bootstrapping Clustered Data," *Journal of the Royal Statistical Society: Series B*, June 2007, pp. 369-390.

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., Liu, T.Y., *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*, Advances in Neural Information Processing Systems (NeurIPS), December 2017, pp. 3146-3154.

Kwolek, B., Kepski, M., "Human Fall Detection on Embedded Platform Using Depth Maps and Wireless Accelerometer," *Computer Methods and Programs in Biomedicine*, December 2014, pp. 489-501.

Lu, C., Shi, J., Jia, J., *Abnormal Event Detection at 150 FPS in MATLAB*, IEEE International Conference on Computer Vision (ICCV), December 2013, pp. 2720-2727.

Oh, S., Hoogs, A., Perera, A. et al., *A Large-Scale Benchmark Dataset for Event Recognition in Surveillance Video*, IEEE Conference on Computer Vision and Pattern Recognition (CVPR), June 2011, pp. 3153-3160.

Tran, D., Wang, H., Torresani, L., Ray, J., LeCun, Y., Paluri, M., *A Closer Look at Spatiotemporal Convolutions for Action Recognition*, IEEE Conference on Computer Vision and Pattern Recognition (CVPR), June 2018, pp. 6450-6459.

Wilson, E.B., "Probable Inference, the Law of Succession, and Statistical Inference," *Journal of the American Statistical Association*, June 1927, pp. 209-212.

Wu, W., Peng, H., Yu, S., "YuNet: A Tiny Millisecond-Level Face Detector," *Machine Intelligence Research*, October 2023, pp. 656-665.
