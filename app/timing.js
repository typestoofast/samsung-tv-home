(function (global) {
  'use strict';

  var key = 'four.startup-timing.v1';
  var maxRuns = 5;
  var maxEvents = 48;
  var maxBytes = 24576;
  var names = ['script-start', 'dom-ready', 'document-loaded', 'handlers-ready',
    'sources-start', 'sources-ready', 'sources-error', 'visibility-hidden',
    'visibility-visible', 'load-frame-1', 'load-frame-2', 'visible-frame-1', 'visible-frame-2'];
  var enabled = global.FourTimingEnabled === true;
  var api = { enabled: enabled, mark: function () {}, clear: function () {},
    export: function () { return { version: 1, enabled: false, runs: [] }; } };
  global.FourTiming = api;
  if (!enabled) return;

  var performance = global.performance;
  var monotonic = performance && typeof performance.now === 'function';
  var started = Date.now();
  var startedTick = monotonic ? performance.now() : 0;
  var origin = performance && (performance.timeOrigin || (performance.timing && performance.timing.navigationStart));
  var run = { startedAtMs: started, timeOriginMs: finite(origin) ? origin : null,
    clock: monotonic ? 'performance' : 'elapsed-wall', events: [] };
  var storage = null;
  var storageFailed = false;
  var runs = [];
  var frameGeneration = 0;
  var domReady = false;
  var loaded = false;

  function finite(value) { return typeof value === 'number' && isFinite(value); }
  function validEvent(event) {
    return event && names.indexOf(event.name) >= 0 && finite(event.atMs) && finite(event.wallMs);
  }
  function previousRuns(text) {
    if (!text || text.length * 2 > maxBytes) return [];
    var value = JSON.parse(text);
    if (!value || value.version !== 1 || !Array.isArray(value.runs)) return [];
    return value.runs.slice(-(maxRuns - 1)).filter(function (item) {
      return item && finite(item.startedAtMs) && (item.timeOriginMs === null || finite(item.timeOriginMs)) &&
        ['performance', 'elapsed-wall'].indexOf(item.clock) >= 0 && Array.isArray(item.events);
    }).map(function (item) {
      return { startedAtMs: item.startedAtMs, timeOriginMs: item.timeOriginMs, clock: item.clock,
        events: item.events.slice(0, maxEvents).filter(validEvent).map(function (event) {
          return { name: event.name, atMs: event.atMs, wallMs: event.wallMs };
        }) };
    });
  }
  try {
    storage = global.localStorage;
    if (storage) runs = previousRuns(storage.getItem(key));
  } catch (error) {
    // Corrupt history or unavailable storage must not stop the launcher.
    storageFailed = true;
  }
  runs.push(run);

  function persist() {
    if (!storage) return;
    var text = JSON.stringify({ version: 1, runs: runs });
    while (text.length * 2 > maxBytes && runs.length > 1) {
      runs.shift();
      text = JSON.stringify({ version: 1, runs: runs });
    }
    if (text.length * 2 > maxBytes) return;
    try { storage.setItem(key, text); }
    catch (error) { storageFailed = true; storage = null; }
  }
  function record(name, elapsed, wall) {
    if (names.indexOf(name) < 0 || run.events.length >= maxEvents) return;
    run.events.push({ name: name, atMs: Math.round(elapsed * 100) / 100, wallMs: wall });
    persist();
  }
  function mark(name) {
    if (names.indexOf(name) < 0 || run.events.length >= maxEvents) return;
    record(name, monotonic ? performance.now() : Date.now() - started, Date.now());
  }
  function frames(prefix) {
    var current = ++frameGeneration;
    if (global.document.hidden || run.events.length >= maxEvents || typeof global.requestAnimationFrame !== 'function') return;
    global.requestAnimationFrame(function () {
      if (current !== frameGeneration || global.document.hidden) return;
      mark(prefix + '-frame-1');
      if (run.events.length >= maxEvents) return;
      global.requestAnimationFrame(function () {
        if (current !== frameGeneration || global.document.hidden) return;
        // A rendering opportunity is not proof of a visible panel frame.
        mark(prefix + '-frame-2');
      });
    });
  }
  function onDomReady() {
    if (domReady) return;
    domReady = true;
    mark('dom-ready');
  }
  function onLoad() {
    if (loaded) return;
    loaded = true;
    onDomReady();
    mark('document-loaded');
    frames('load');
  }
  api.mark = mark;
  api.export = function () {
    return JSON.parse(JSON.stringify({ version: 1, enabled: true, storageFailed: storageFailed, runs: runs }));
  };
  api.clear = function () {
    frameGeneration += 1;
    run.events = [];
    runs = [run];
    if (!storage) return;
    try { storage.removeItem(key); }
    catch (error) { storageFailed = true; storage = null; }
  };
  record('script-start', startedTick, started);
  global.document.addEventListener('DOMContentLoaded', onDomReady);
  global.addEventListener('load', onLoad);
  global.document.addEventListener('visibilitychange', function () {
    if (run.events.length >= maxEvents) return;
    mark(global.document.hidden ? 'visibility-hidden' : 'visibility-visible');
    if (global.document.hidden) frameGeneration += 1;
    else frames('visible');
  });
  if (global.document.readyState !== 'loading') onDomReady();
  if (global.document.readyState === 'complete') onLoad();
}(window));
