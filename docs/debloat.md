# Samsung cleanup results and limits

Tested on QN65Q70TAFXZC, Tizen 5.5.0, firmware T-NKMAKUC-2743.0 on
6-7 November 2026. No Samsung package was disabled or uninstalled.

CleanYourTV's Android lists group ACR/viewing trackers, telemetry, promotional
content and launchers, preloaded apps, and unused optional features. Its reversible
`pm disable-user` mechanism does not exist on Tizen. The equivalent components on
this TV require separate inspection and a tested restore route.

| Android list category | Observed Samsung counterpart | Result on this TV |
|---|---|---|
| Stock Home and recommendation rows | Samsung FirstScreen, `com.samsung.tv.csfs` | Physical short Home opens Four without Samsung's bar. Samsung Home stays available explicitly. |
| ACR/viewing-data collection | `acr`, `contents-recognition-service`, `vision-data-recognition-service` | Services were running. Owner reported Viewing Information Services consent already off. No process disable or network-traffic reduction claimed. |
| Advertising/promotion services | `pisa-service`, `adagent-service` | Running. Vendor disable-marker directory is root-owned and not writable by the SDK user. Left intact. Interest-Based Advertisements consent was already off. |
| Free-channel promotion | `slive-provider-daemon`, Samsung TV Plus | Autorun Samsung TV Plus was already off. Backend remained running. |
| Unused casting features | Multi View autorun for mirroring and casting | Both stored Int32 settings changed from 1 to 0. Each was restored to 1 and verified before applying 0. UI labels had previously been confirmed on the TV. |
| Unused apps, voice, AirPlay, SmartThings | Installed app and service inventory | Owner does not use these. No reliable package-disable/enable pair was established, so they remain installed and enabled. |

The two changed settings were
`db/menu/general/smart_features/autorun_multiview_mirroring` and
`db/menu/contentcasting/multiview_autorun`. Use the TV's General > Smart Features
menu where available. This repository does not ship a native settings writer.
Keep your own before values; restoring this owner's values is not a universal
restore procedure.

## Package deactivation experiment

An inert, source-built signed test app was installed to test `pkgcmd` without
touching Samsung packages. App deactivation returned success, and the official
launcher subsequently reported the app unavailable for user 5001. The matching
app activation failed to find its app information; package activation failed too.
Reinstalling the same signed test package recovered it, and official launch then
succeeded.

The inspected database flags did not reflect that availability change, so they
were not a valid standalone verification signal. This result does not establish
a reusable restore path for preloaded packages. There is deliberately no Samsung
package list or disable command in this project. Disabling an unknown component
and hoping to reinstall it is not equivalent to CleanYourTV's Android workflow.

Research on a related Q70T describes deeper service disabling using root and boot
patches. Those operations are outside this project. The fact that a service runs
does not establish that it is sending data, and a consent opt-out does not prove
that its process has stopped.

## Performance

There is no measured speedup claim. One captured boot log placed panel power-on
at 11.780 seconds and app readiness at 13.791 seconds after kernel startup. That
log was not synchronized with a physical Power press. Steady-state samples showed
84-94% CPU idle and no I/O wait; they do not measure boot-time contention.

Four's small interface and verified Home route remove navigation through the
stock Home bar. The Home route survived one long-Power restart. Samsung's bar
appeared at startup, and the owner then pressed Home to open Four. Automatic
startup did not work in that trial, despite the first-screen and autorun settings
retaining the requested values.

That restart also recorded the full web-app runtime becoming ready at 38.918
seconds after kernel startup. Four's manually opened process was observed at
about 37 seconds on the startup log clock, while that runtime was still starting.
These events identify a startup dependency; they do not measure first visible
frame or establish a speedup. The runtime may have started on demand after the
late manual request, so 38.918 seconds is not a proven startup floor. Panel startup, HDMI negotiation, shutdown, and
Stremio playback have no demonstrated improvement.

Version 0.2.1 skips a redundant source-selection call when reopening the current
HDMI input. The fallback and different-input paths pass automated tests. Visible
input-switch timing has not been measured.

A separately signed C helper was accepted for installation but refused execution
by the TV's native executable-signature policy. It did not replace the working
.NET companion. An inert managed update replaced the test executable, and the
failed loader exited. No security policy was changed.

The subsequent ordinary-Power report also required a Home press to open Four.
Fresh logs could not be retrieved because the TV was unreachable. See the
[performance work](performance.md) for the installed 0.2.2 responsiveness changes,
the owner's successful Home/navigation/Apple TV test, app timings, and remaining
measurement gaps.

The comparison used CleanYourTV's
[Xiaomi Mi TV 4A list](https://github.com/Gathin23/cleanyourtv/blob/main/examples/xiaomi-mi-tv-4a/debloat.txt),
[Sony BRAVIA list](https://github.com/Gathin23/cleanyourtv/blob/main/examples/sony-bravia-4k-gb-us/debloat.txt)
and [privacy guidance](https://github.com/Gathin23/cleanyourtv/blob/main/docs/privacy.md).
The separate [Q70T research report](https://github.com/cfloinc/samsung-q70t-tizen-root/blob/main/DEBLOAT-STATE.md)
is evidence of a different setup, not instructions or a compatibility claim for
this project.
