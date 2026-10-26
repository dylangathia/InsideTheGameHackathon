# Auto-eventing from video

Run on 26 October 2026: 9000 video frames (15 minutes of play at 10 fps) in 1364 s. Regenerate with `python cli.py autoevent` in `backend/`.

The brief suggests "running a model over an incoming video feed to generate the pass and speed metrics automatically, rather than tagging them by hand". Because our matches are synthetic, we know the exact truth of every event, so we can measure the result.

**How it works** ([backend/footie/vision/autoevent.py](../backend/footie/vision/autoevent.py)):

1. **Camera:** the match is rendered as a top-down video feed with sensor noise, blur, camera shake, lighting drift, dropped frames (3%) and a ball that is sometimes hidden (4%).
2. **Detector:** computer vision finds players by kit colour and the ball as a small round bright blob, from the pixels alone. It never sees the tracking data.
3. **Events:** the ball is tracked frame to frame; fast movement (over 8 m/s) is a flight. Each flight becomes a pass (distance, ball speed) or, if it ends at the goal mouth, a shot (shot speed). Possession is chained from receiver to the next passer.
4. **Evaluation:** each true pass and shot is matched to a detection that starts within 0.6 s.

## Results

| Measure | Result |
|---|---|
| Passes detected | **155 of 157 (99%)** |
| Shots detected | **4 of 5 (80%)** |
| Detections that were real events (precision) | 96% |
| Pass distance error | **1.2 m** on average |
| Ball speed error | **2.3 km/h** on average |
| Shot speed error | **14.3 km/h** on average |
| Pass completed or lost | 69% correct, but always guessing "completed" scores 79%, so this part is **not yet useful** |

## By match window (5 minutes each, around goals)

| Match | Passes found | Shots found | Precision | Distance error | Ball speed error | Shot speed error |
|---|---|---|---|---|---|---|
| The Comeback | 100% of 50 | 50% of 2 | 98% | 1.0 m | 2.3 km/h | 9.5 km/h |
| Ten Men | 100% of 46 | 100% of 1 | 98% | 1.6 m | 2.2 km/h | 16.4 km/h |
| Late Drama | 97% of 61 | 100% of 2 | 94% | 1.3 m | 2.3 km/h | 15.7 km/h |

An annotated clip (the 8' opener in The Comeback, a 7-pass move ending in a goal, with every detection drawn on the frames) is in [media/auto-eventing.mp4](media/auto-eventing.mp4).

## Limits

- **Not tested on real footage.** A clean top-down render is far easier than broadcast video, which has camera pans, perspective, crowds and heavy occlusion. This shows and measures the method; it is not a claim of real-world accuracy.
- **Classic computer vision, not a trained model.** A production system would use a trained detector (e.g. a YOLO-style model) for players and the ball; the event logic downstream would stay the same.
- **Pass outcome is weak.** Telling a completed pass from a lost one needs reliable player identity at the moment of the pass; our colour-only detection can't separate a passer from a defender pressing them.
- The ingest stage accepts any event source, so a production auto-eventing model could replace the synthetic engine without changing the rest of the pipeline.
