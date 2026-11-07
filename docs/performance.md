# Performance work and measurement

Version 0.2.2 was installed on the test TV on 7 November 2026. The owner completed
a Home, navigation, and Apple TV test and reported that it felt very fast.
Automatic startup remains unresolved, and no before/after speedup is established.

The input path now handles three cases without extra button presses:

- Reopening the current HDMI input skips a redundant source-selection request.
- An HDMI selection made before initial discovery finishes waits for that result
  and then opens the requested input. Back cancels it.
- Returning to Four reuses the last verified input list while a fresh read runs.
  Source discovery cannot cancel a Stremio launch or an input handoff.

The UI uses local assets and has no animation, network request, or deliberate
rendering delay. Its eight-second API deadlines are error timeouts. They do not
delay drawing the shortcuts. These code properties do not measure TV response.

## Recorded on the Q70T

One saved diagnostic run on QN65Q70TAFXZC, Tizen 5.5.0,
T-NKMAKUC-2743.0 recorded:

| Interval | Time |
|---|---:|
| Page navigation origin to input handlers ready | 530.4 ms |
| Page navigation origin to second frame callback | 611.4 ms |
| Page navigation origin to HDMI inventory ready | 639.6 ms |
| Warm visibility event to second frame callback | 71.3 ms |
| Warm visibility event to refreshed HDMI inventory | 81.3 ms |

These are app timings from one run, not a benchmark distribution. A frame callback
is a rendering opportunity, not a measured visible frame. They exclude the time
from pressing Home to starting page navigation and do not establish input-to-picture
latency. The diagnostic recorder itself adds local-storage overhead. The physical
test and these internal intervals are separate evidence; the retained logs do not
pair every physical key with a page event.

## What the captured startup established

On the tested Q70T, Samsung Home is a vendor-managed application that requests
ahead-of-time .NET code. Four is an ordinary web application. They use different
launch paths. Copying Samsung's private application type or boot settings is not
a supported optimization for a third-party application.

In one long-Power restart, the full web-app runtime reported ready at 38.918
seconds after kernel startup. The owner manually pressed Home to open Four.
That late runtime marker is **not a proven 39-second startup floor**: the engine
may have started on demand after the late request. We need the launch-request
timestamp, engine initialization, page readiness, and an observed visible frame
from the same run to attribute the delay.

Both owner-reported power tests required Home to open Four. Automatic startup
is not solved. No safe stock-bar suppression and automatic Four startup pair
has passed hardware testing. No reduction in panel startup or shutdown time is
claimed. See [the cleanup results](debloat.md) for the separate native-helper
experiment and its executable-policy refusal.

## Build a diagnostic package

Normal builds do not load the timing recorder. A diagnostic build explicitly
enables local recording. It has no network access, polling, background service,
or additional privilege. It retains at most five runs, 48 fixed events per run,
and 24 KiB in the app's local storage. It records no source names or device IDs.
Storage writes add overhead, so compare diagnostic runs against diagnostic runs.

Using the same private source export as [normal packaging](../README.md):

```sh
python3 tools/stage-app.py --inputs .local/tv-input-names.json \
  --out .local/diagnostic-stage --model QN65Q70TAFXZC \
  --firmware T-NKMAKUC-2743.0 --diagnostics
tizen build-web -- .local/diagnostic-stage
tizen package -t wgt -s YOUR_PROFILE -o /absolute/private/signed-output \
  -- .local/diagnostic-stage/.buildResult
```

Omit `--diagnostics` to stage a normal build. Each staging directory must be new.
The tool copies only the application files and validated input bindings; it
does not install anything or connect to a TV. Keep the staged output private.

The recorder saves script start, DOM readiness, handler readiness, input-query
start and completion, document load, visibility changes, and two animation-frame
callbacks after load or return. Read the saved result through Four's Web Inspector:

```js
JSON.stringify(FourTiming.export())
```

`FourTiming.clear()` clears that history. Installing a normal build stops new
recording. A frame callback is only a rendering opportunity, not proof that pixels
reached the panel. Page timings also cannot measure time before the web engine
starts. Pair these records with the TV's launch logs; use physical video for an
actual button-to-visible-response measurement.

## Hardware checks before claiming an improvement

Use the same remote, awake source, standby interval, and previous app for each
comparison. Keep first launch separate from warm returns. Preserve slow runs.
Check that Home opens Four, Samsung Home remains accessible, Source/Input works,
all four destinations open, and Back cancels a pending selection. A faster API
acknowledgement does not establish a faster visible HDMI picture.
