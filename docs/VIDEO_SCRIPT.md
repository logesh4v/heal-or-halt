# Heal or Halt: demo video (target 2:50, hard limit 3:00)

> **Automatic version:** `make serve`, then `make video`. The agent runs the same four beats live and records them with on-screen subtitles and no sound (`HOH_VIDEO_SOUND=1 make video` adds a synthetic voice), writing `results/heal-or-halt-demo.mp4` (about 2:26). Use the manual script below only if you want your own voice and screen.

Everything on screen is a **real run**: real Playwright, real Decider on this Mac, real Amazon Nova on Bedrock.
Nothing is edited into the terminal. Timings below are from the rehearsal on 11 Oct 2026.

## A. Before you record (10 minutes, once)

Run each command on its own line and wait for it to finish.

1. Quit Chrome windows you don't need, Slack, Docker and other heavy apps. Decider needs about 5 GB.
2. Terminal: font size 20 or more, window at least 150 columns wide, dark theme, and clear the history so no old output shows.
3. Turn on Do Not Disturb (Control Centre → Focus), so no notifications appear in the recording.
4. Start Decider (the server is ready in about 15 seconds):

   ```
   cd ~/Logesh/Project/heal-or-halt
   make serve
   ```

5. The preflight must print `READY`. If any line says FAIL, fix it before you record:

   ```
   make check
   ```

6. Create the fresh, green practice repo (rerun this before every retake):

   ```
   make playground
   ```

7. Open these in tabs so you can switch to them quickly:
   - `playground/app/index.html` in your editor (Kiro or VS Code), scrolled to the line `<button id="split" type="submit">Split bill</button>`
   - `docs/ARCHITECTURE.md`, previewed so the diagram renders
   - `results/EVAL.md`
8. Do one silent dry run of section C, then run `make playground` again before the real take.

## B. How to record

**Video:** press **Cmd + Shift + 5** → *Record Entire Screen* (or *Record Selected Portion* around the terminal and editor) → **Options** → Microphone: choose your mic → Save to: Desktop → **Record**. To stop, click the stop button in the menu bar.

**Voice, two ways:**
- **Live (simplest):** talk while you record, using the lines below. You don't need to read word for word.
- **Voice-over (cleaner):** record the screen silently, then open the file in iMovie, add the narration with the mic button, and trim any pauses. Total time must stay under 3:00.

**Upload:** put it on YouTube as *Unlisted* until 16 Oct, then switch it to *Public*. Turn on auto-captions. Don't add copyrighted music.

## C. Shot list and narration

| Time | On screen (what you do) | Say |
|---|---|---|
| **0:00 – 0:12** | The editor with SplitPay's button line | "Someone renames one button. Every UI test goes red. Is the product broken, or only the test? A human usually decides. This agent does, and it knows when to say no." |
| **0:12 – 0:30** | `docs/ARCHITECTURE.md` diagram | "Heal or Halt is one Strands agent. The decision comes from Strands Decider 2B, running locally on this laptop with a confidence number. Amazon Nova on Bedrock writes the fix. Plain code checks everything: no PR without a green re-run." |
| **0:30 – 0:40** | In the editor, change `Split bill` to `Calculate shares` and save. In the terminal: `git -C playground commit -qam "copy: rename the main button"` | "Here's a real change: the button now says Calculate shares. I commit it." |
| **0:40 – 1:05** | `make run` (about 17 s). Point at `can_heal 0.92 -> HEAL`, `[rerun] GREEN`, `PROCEED open_pr` | "Three tests fail. Decider: can it heal? Point nine two, heal. Nova writes the new locator, the gate checks it, the whole suite re-runs green, and only then does a PR open." |
| **1:05 – 1:15** | `cat playground/PR-1.md`, scrolled to *Receipt* | "Every PR has a receipt: the confidence, the before-and-after of the page, and the re-run. The facts are written by code, not by the model." |
| **1:15 – 1:25** | `git -C playground merge -q heal/split-bill-to-calculate-shares`, then in the editor change `(total / people)` to `(total * people)`, save, and `git -C playground commit -qam "refactor: tidy share calculation"` | "I merge that. Now I quietly break the maths and call it a refactor." |
| **1:25 – 1:45** | `make run` (about 11 s). Point at `HALT (assertion failed ...)` and `owner=developer` | "Two tests fail. This time the value on screen is wrong, and a wrong value is never healed. Halt. An issue goes to the developer. No code was touched." |
| **1:45 – 2:10** | `make agent M=combo-rename-math` (about 20 s). Point at HEAL 0.91, then `[rerun] RED`, then the issue | "The hardest case: a rename and a maths bug in one commit. Decider is right that the button was renamed, so it says heal. But the re-run is still red, so the gate refuses the PR. The rename was hiding a real bug." |
| **2:10 – 2:30** | `make agent M=test-typo-button` (about 15 s). Point at `0.57 -> ASK`, `Nova Pro ... UNSAFE`, `HALT` | "Here the test itself has a typo. Decider isn't sure: point five seven, the grey zone. A bigger model, Nova Pro, gets a vote, but only to say no. It can never turn a halt into a heal." |
| **2:30 – 2:48** | `results/EVAL.md` table | "On 48 failures it never saw during tuning, it healed all 27 fixable ones and made zero wrong heals. Decider without the rules made 11, a simple rename rule made 3, and Nova Micro made 3. The full agent got all 34 kinds of breakage right." |
| **2:48 – 2:58** | The `patterns/policy-can-heal/` folder | "The decision is a reusable pattern: a question, the rules, and a threshold picked from data. Copy it in front of any agent that changes code. Heal when it's safe, halt when it's not." |

**On-screen rule:** every decision line shows its confidence number (`can_heal 0.92`). The hackathon asks for that, so keep those lines visible and don't scroll past them quickly.

## D. If something goes wrong during a take

| Problem | Fix |
|---|---|
| `make run` says "commit your change first" | You saved but didn't commit. Run the `git -C playground commit ...` line |
| `make run` says "check out main" | Run `git -C playground checkout main` |
| Decider is slow (more than 3 s per decision) | Memory is low. Quit apps, then run `make stop` and `make serve` |
| `make check` says bedrock FAIL | Your AWS session expired. Refresh your credentials in another terminal, then run `make check` again |
| You want a clean retake | Run `make playground`. It rebuilds the green repo from scratch |

## E. After recording

1. `make stop` frees about 5 GB of memory.
2. Watch the whole video once without sound. Every decision should still be readable.
3. Check that no notification, email, AWS account number or token appears in any frame.
