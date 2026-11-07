(function (global) {
  'use strict';
  var tv = global.tizen;
  var generation = 0;
  var pendingTimer = null;
  var sourceGeneration = 0;
  var sourceTimer = null;
  var inventory = [];

  function message(error) {
    return error && (error.message || error.name) || 'The TV did not complete the request.';
  }

  function begin(done) {
    generation += 1;
    var current = generation;
    clearTimeout(pendingTimer);
    function finish(error, value) {
      if (current !== generation) return;
      generation += 1;
      clearTimeout(pendingTimer);
      pendingTimer = null;
      done(error, value);
    }
    pendingTimer = setTimeout(function () { finish('The TV did not respond. Try again.'); }, 8000);
    return { live: function () { return current === generation; }, finish: finish };
  }

  function cancel() {
    generation += 1;
    clearTimeout(pendingTimer);
    pendingTimer = null;
    sourceGeneration += 1;
    clearTimeout(sourceTimer);
    sourceTimer = null;
  }

  function sources(done) {
    if (!tv) { done(null, []); return; }
    sourceGeneration += 1;
    var current = sourceGeneration;
    clearTimeout(sourceTimer);
    function finish(error, list) {
      if (current !== sourceGeneration) return;
      sourceGeneration += 1;
      clearTimeout(sourceTimer);
      sourceTimer = null;
      done(error, list);
    }
    sourceTimer = setTimeout(function () { finish('The TV inputs did not respond. Try again.'); }, 8000);
    try {
      tv.systeminfo.getPropertyValue('VIDEOSOURCE', function (data) {
        if (current !== sourceGeneration) return;
        inventory = [];
        ['connected', 'disconnected'].forEach(function (state) {
          (data[state] || []).forEach(function (source) {
            if (source.type !== 'HDMI') return;
            if (inventory.some(function (item) { return item.number === source.number; })) return;
            inventory.push({ number: source.number, name: source.editName || '', connected: state === 'connected', raw: source });
          });
        });
        inventory.sort(function (a, b) { return a.number - b.number; });
        finish(null, inventory);
      }, function (error) { finish(message(error)); });
    } catch (error) { finish(message(error)); }
  }

  function launch(id, done) {
    if (!tv) { done('Open Four on the TV to launch this shortcut.'); return; }
    var operation = begin(done);
    try {
      tv.application.launch(id, function () { operation.finish(null); }, function (error) { operation.finish(message(error)); });
    } catch (error) { operation.finish(message(error)); }
  }

  function input(number, done) {
    if (!tv) { done('Open Four on the TV to switch inputs.'); return; }
    var source = inventory.filter(function (item) { return item.number === number; })[0];
    if (!source) { done('This HDMI input is unavailable.'); return; }
    var operation = begin(done);
    function openViewer() {
      try {
        tv.application.launch('org.tizen.tv-viewer', function () { operation.finish(null); }, function () {
          operation.finish('Input selected, but the TV picture did not open. Use Samsung Home to select the input.');
        });
      } catch (error) { operation.finish(message(error)); }
    }
    var current = null;
    try {
      if (typeof tv.tvwindow.getSource === 'function') current = tv.tvwindow.getSource('MAIN');
    } catch (error) {
      // A failed current-source read must not prevent the normal switch.
      current = null;
    }
    if (current && current.type === 'HDMI' && current.number === number) {
      openViewer();
      return;
    }
    try {
      tv.tvwindow.setSource(source.raw, function (selected) {
        if (!operation.live()) return;
        if (selected && (selected.type !== 'HDMI' || selected.number !== number)) {
          operation.finish('The TV selected a different input.');
          return;
        }
        openViewer();
      }, function (error) { operation.finish(message(error)); }, 'MAIN');
    } catch (error) { operation.finish(message(error)); }
  }

  function match(key, list) {
    var names = { apple: /^(apple\s*tv)(\s*\([^)]*\))?$/i, switch: /^(nintendo\s*)?switch(\s*2)?$/i, steam: /^steam(\s*machine)?$/i };
    var matches = list.filter(function (source) { return names[key] && names[key].test(source.name.trim()); });
    return matches.length === 1 ? matches[0].number : null;
  }

  global.FourDevice = { sources: sources, launch: launch, input: input, cancel: cancel, match: match, available: !!tv };
}(window));
