(function () {
  'use strict';
  var device = window.FourDevice;
  var shortcuts = Array.prototype.slice.call(document.querySelectorAll('.destination'));
  var samsung = document.getElementById('samsung');
  var status = document.getElementById('status');
  var selected = shortcuts[0];
  var lastShortcut = 0;
  var busy = false;
  var inputs = [];
  var inputsReady = false;
  var discovering = false;
  var queuedInput = null;
  var bindings = window.FourInputMap || {};
  var labels = { apple: 'Apple TV', switch: 'Switch 2', stremio: 'Stremio', steam: 'Steam' };

  function mark(name) {
    if (window.FourTiming) window.FourTiming.mark(name);
  }
  function focus(button) {
    if (selected) selected.tabIndex = -1;
    selected = button;
    button.tabIndex = 0;
    button.focus();
    var index = shortcuts.indexOf(button);
    if (index >= 0) lastShortcut = index;
  }
  function finish(error) {
    busy = false;
    document.body.classList.remove('busy');
    status.textContent = error || '';
  }
  function act(label, action) {
    if (busy) return;
    busy = true;
    document.body.classList.add('busy');
    status.textContent = 'Opening ' + label + '...';
    action(finish);
  }
  function portFor(key) {
    var discovered = device.match(key, inputs);
    if (discovered !== null) return discovered;
    var binding = bindings[key];
    if (binding && inputs.some(function (input) { return input.number === binding.port; })) return binding.port;
    return null;
  }
  function discover() {
    if (discovering) return;
    discovering = true;
    mark('sources-start');
    device.sources(function (error, list) {
      mark(error ? 'sources-error' : 'sources-ready');
      discovering = false;
      if (error) {
        if (queuedInput !== null || !busy) finish('Could not read the TV inputs. ' + error);
        queuedInput = null;
        return;
      }
      inputs = list;
      inputsReady = true;
      if (queuedInput !== null) {
        var key = queuedInput;
        queuedInput = null;
        openInput(key);
      }
    });
  }
  function openInput(key) {
    var port = portFor(key);
    if (port === null) { finish(labels[key] + ' could not be found among the TV inputs.'); return; }
    device.input(port, finish);
  }

  shortcuts.forEach(function (shortcut) {
    shortcut.addEventListener('click', function () {
      if (busy) return;
      focus(shortcut);
      var key = shortcut.getAttribute('data-key');
      if (key === 'stremio') {
        act(labels[key], function (done) { device.launch('IkWsFHtOY9.Stremio', done); });
        return;
      }
      if (!device.available) { finish('Open Four on the TV to use this shortcut.'); return; }
      act(labels[key], function () {
        if (inputsReady) { openInput(key); return; }
        queuedInput = key;
        discover();
      });
    });
  });
  samsung.addEventListener('click', function () {
    act('Samsung Home', function (done) { device.launch('com.samsung.tv.csfs', done); });
  });
  document.addEventListener('focusin', function (event) {
    if (event.target.tagName === 'BUTTON' && event.target !== selected) focus(event.target);
  });
  document.addEventListener('keydown', function (event) {
    var key = event.keyCode;
    if ([13, 27, 37, 38, 39, 40, 10009].indexOf(key) < 0) return;
    event.preventDefault();
    if (busy) {
      if (key === 27 || key === 10009) {
        queuedInput = null;
        discovering = false;
        device.cancel();
        finish('Request cancelled. An input already selected may remain active.');
      }
      return;
    }
    if (key === 13) { selected.click(); return; }
    if (key === 27 || key === 10009 || key === 40) { focus(samsung); return; }
    if (selected === samsung) {
      if (key === 38) focus(shortcuts[lastShortcut]);
      return;
    }
    if (key === 37 || key === 39) {
      var next = shortcuts.indexOf(selected) + (key === 37 ? -1 : 1);
      focus(shortcuts[Math.max(0, Math.min(shortcuts.length - 1, next))]);
    }
  });
  document.addEventListener('visibilitychange', function () {
    queuedInput = null;
    discovering = false;
    device.cancel();
    finish();
    if (!document.hidden) { focus(shortcuts[lastShortcut]); discover(); }
  });
  focus(shortcuts[0]);
  mark('handlers-ready');
  discover();
}());
