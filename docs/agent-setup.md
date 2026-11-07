# Set up an owner's home

The agent gathers the TV's sources and installed apps, resolves their names,
finds local logos, and generates a private home configuration. The owner should
not have to fill in a port-assignment form.

Discovery has a limit on the tested QN65Q70TAFXZC, firmware T-NKMAKUC-2743.0.
Samsung's public source API reports HDMI numbers but omits the saved names.
An existing name export or the TV's Sources screen can supply those names.
If neither is accessible, ask about only the unresolved ports. Do not present
this workflow as universal automatic device detection.

## 1. Collect evidence

Record the model, firmware and Tizen version. Check the current checkout and
existing installation before selecting an application identity or signing an
update. Keep all owner records under `.local/`.

Run `tools/discover-inputs.js` in Samsung Web Inspector for an inspectable TV
app with the required API access. The script reads HDMI sources and installed
application information. It does not switch inputs or launch apps. Keep both
connected and disconnected HDMI entries, since a sleeping device may appear
disconnected. Preserve API errors as missing evidence.

The script collects once, prints the completed JSON and stores it in
`FourDiscovery.result`. Each API has an eight-second timeout. After the result
appears, export it from the Inspector console:

```js
JSON.stringify(FourDiscovery.result)
```

Save the JSON as `.local/inventory.json`. Call `FourDiscovery.collect(callback)`
only when a fresh inventory is needed. Check the new result in the callback;
the previous result remains available while collection runs. The inventory
shape is:

```json
{
  "schemaVersion": 1,
  "sources": [{ "port": 3, "name": "Apple TV", "connected": true }],
  "apps": [{ "id": "observed.exactId", "name": "Stremio", "iconPath": "" }],
  "errors": []
}
```

The example values are not defaults. Replace them with observed records. Errors
have `api`, `code` and `message` fields. Do not turn a failed API read into an
empty successful inventory.

There is no bootstrap installer or native-name collector in this workflow. An
authorized Inspector session, a previously captured inventory, or accessible TV
Sources and installed-app information must be available first. If these are
unavailable, explain the missing access and collect the evidence before making
a final home. Do not generate the example owner's home as a fallback.

Use exact installed app IDs for launch targets. A TV app named Apple TV and an
Apple TV box on HDMI are separate destinations. A package name copied from a
different TV is not evidence that an app is installed on this one.

If HDMI names are missing, use the first available source of evidence:

1. An existing private native source export with saved names and source IDs.
   Prefer a nonempty saved `EditName` to `DetectedName`. Keep the raw record and
   model/firmware beside the derived mapping. Native `SourceType` values are
   device-specific. On the tested QN65Q70TAFXZC with T-NKMAKUC-2743.0 only,
   values 13-16 map to HDMI 1-4. Verify that identity before normalizing those
   records into the inventory format. The setup tool does not convert native
   source IDs.
2. The TV's Sources screen, accessed through an available owner-authorized
   interface. Record each visible label beside its HDMI number. Do not open
   factory menus or change source names to make discovery easier.
3. One focused owner clarification for what remains unknown. For example, ask
   which of two identically named consoles is on HDMI 2. Do not ask the owner to
   reconstruct mappings already visible in the evidence.

This repository does not provide a supported native-name export collector.
The original Q70T export came from an undocumented developer interface. Do not
reproduce that access through a private shell, root or command injection.

## 2. Resolve the destinations

Generate a private plan from the inventory:

```sh
python3 tools/setup-home.py \
  --inventory .local/inventory.json --out .local/home.json
```

The output file must be new. Keep the previous plan when refreshing an inventory.
This includes HDMI destinations. Add `--apps Stremio Netflix` only when those
apps are wanted; the tool resolves their exact IDs from the inventory. Without
`--apps`, it does not include installed apps. `--exclude-ports 1` explicitly
omits a port the owner does not want. The generated home supports 1-8 shortcuts.
Do not add every system app or copy another owner's choices.

Match labels against the observed names and app IDs. Keep generic names such as
HDMI, PC or Game Console unresolved when they do not identify the device. Treat
duplicate names and conflicting evidence the same way. Do not silently pick
the first match, assume the example's HDMI order, or choose a logo as evidence
of the device.

Each proposed tile needs a display label, a concrete HDMI or app launch target,
and its evidence. Resolve each unresolved entry or explicitly exclude it from
the requested home. Record exclusions and their reasons beside the private plan;
the generator does not retain excluded ports. Refresh the inventory after moving
cables, renaming inputs or installing apps.

The plan has `schemaVersion`, `shortcuts` and `unresolved` fields. The command
exits with code 2 while entries remain unresolved. Read those entries instead
of treating a written JSON file as a completed setup. A resolved shortcut looks
like one of these:

```json
[
  {"key":"hdmi-3","label":"Apple TV","kind":"hdmi","port":3,"sourceName":"Apple TV","logo":"appletv"},
  {"key":"app-0","label":"Stremio","kind":"app","appId":"observed.exactId","logo":"stremio"}
]
```

These are example entries for the `shortcuts` array. Keep the original inventory
unchanged.
When resolving a generic name or duplicate, save the new source evidence or
owner clarification privately. Add or update the matching shortcut and remove its
unresolved entry only after that evidence establishes the target.

## 3. Gather logos

Reuse matching files from `app/assets/` when available. Their sources are in
`app/assets/SOURCES.json`. For another destination, prefer the vendor's official
brand asset or a versioned icon source with clear reuse terms. Download it on
the setup computer and package the local file. Do not hotlink images.

Record the asset's source URL and version, checksum, license or usage terms,
and any changes such as recoloring. Preserve required notices. Bundled logo keys
are `appletv`, `nintendoswitch`, `steam` and `stremio`. A custom logo must be a PNG
of at most 256 KiB and 1024 pixels per dimension. Save it relative to the home
JSON and use this object for the shortcut's `logo` field:

```json
{"file":"logos/ps5.png","source":"https://official-source-page","license":"usage terms"}
```

Replace the example source and license with the actual source and terms. The
staging tool copies the image and attribution into the local app. Keep the
checksum and any transformation details in the private evidence record.
Every shortcut requires a bundled logo or sourced PNG. Keep `missing_logo`
unresolved until an appropriate asset is available.

## 4. Preview and package

Stage the resolved home under a new `.local/` directory. Serve that directory
locally and inspect the generated labels, logos, tile order, focus and Samsung
Home button. Use arrows, Enter and Escape. A browser cannot verify a TV action.

```sh
python3 tools/stage-app.py --home .local/home.json --out .local/stage
python3 -m http.server 4796 --bind 127.0.0.1 --directory .local/stage
```

Open `http://127.0.0.1:4796`. The `--home` path uses normalized public HDMI port
numbers and does not need the legacy model flags. `--inputs` remains available
for the original, explicitly scoped Q70T name-import workflow.

Show the generated preview and its destination list before deployment. Resolve
any remaining identity or mapping ambiguity before signing. Keep the tracked
example unchanged; owner bindings and downloaded personal assets belong in the
private build.

Use Samsung's official certificate tools and an owner-controlled TV Public
profile containing the target TV's DUID. Build and sign the staged directory
with Tizen CLI. Keep the previous signed app and private configuration for an
update rollback. A signing or installation refusal is a stop condition.

## 5. Verify on the TV

Open each included destination and check that it reaches the intended device
or app. Check D-pad movement at every edge, return to the dashboard, and the
explicit Samsung Home button. Confirm with the physical remote when testing a
physical button. An API success callback alone does not prove the right picture
appeared.

Record the model, firmware, configuration and results privately. Mark failed or
untested destinations as such. Report dashboard behavior separately from Home
routing and automatic startup. The dashboard alone does not replace Samsung
Home, and automatic startup has not worked in the recorded Q70T trials.

If physical Home routing is part of the owner's request, follow
[its separate baseline and recovery procedure](home-route.md). Preserve the
working route during ordinary home customization. Never uninstall its carrier.
