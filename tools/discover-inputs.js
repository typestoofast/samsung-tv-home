/* Paste into Four's Web Inspector. The result stays in memory and the console.
 * Export again with JSON.stringify(window.FourDiscovery.result, null, 2).
 * Public fields and methods:
 * https://developer.samsung.com/smarttv/develop/api-references/tizen-web-device-api-references/systeminfo-api.html
 * https://developer.samsung.com/smarttv/develop/api-references/tizen-web-device-api-references/application-api.html
 * VIDEOSOURCE has no documented name field. editName is best effort only;
 * the tested Q70T does not supply it. Empty names must not be inferred from ports.
 */
(function (global) {
  'use strict';
  var discovery = { collect: collect, result: null };

  function collect(callback) {
    if (typeof callback !== 'function') throw new TypeError('A discovery callback is required.');
    var result = { schemaVersion: 1, sources: [], apps: [], errors: [] };
    var remaining = 2;
    var errors = Object.create(null);
    var tv = global.tizen;

    function error(api, code, message) {
      var key = api + ':' + code;
      if (errors[key]) return;
      errors[key] = true;
      result.errors.push({ api: api, code: code, message: message });
    }
    function text(value) { return typeof value === 'string' ? value.trim() : ''; }
    function merge(entry, incoming, fields, api) {
      fields.forEach(function (field) {
        if (!incoming[field] || entry.conflicts[field]) return;
        if (entry.value[field] && entry.value[field] !== incoming[field]) {
          entry.value[field] = '';
          entry.conflicts[field] = true;
          error(api, 'ConflictingData', 'Duplicate records disagree. Conflicting text fields were left empty.');
        } else entry.value[field] = incoming[field];
      });
    }
    function readSources(data) {
      var byPort = Object.create(null);
      ['connected', 'disconnected'].forEach(function (state) {
        var list = data && data[state];
        if (!Array.isArray(list)) {
          error('sources', 'InvalidData', 'A video-source list was missing or invalid.');
          return;
        }
        list.forEach(function (source) {
          if (!source || typeof source.type !== 'string') {
            error('sources', 'InvalidData', 'Invalid video-source records were omitted.');
            return;
          }
          if (source.type !== 'HDMI') return;
          var port = source.number;
          if (typeof port !== 'number' || !isFinite(port) || port < 1 || port > 2147483647 || Math.floor(port) !== port) {
            error('sources', 'InvalidData', 'HDMI records with invalid port numbers were omitted.');
            return;
          }
          var value = { port: port, name: text(source.editName), connected: state === 'connected' };
          var existing = byPort[port];
          if (!existing) byPort[port] = { value: value, conflicts: {} };
          else {
            merge(existing, value, ['name'], 'sources');
            if (existing.value.connected !== value.connected) {
              error('sources', 'ConflictingData', 'A port appears in both source lists. The connected list takes precedence.');
            }
            existing.value.connected = existing.value.connected || value.connected;
          }
        });
      });
      return Object.keys(byPort).map(function (port) { return byPort[port].value; })
        .sort(function (a, b) { return a.port - b.port; });
    }
    function readApps(data) {
      var byId = Object.create(null);
      if (!Array.isArray(data)) {
        error('apps', 'InvalidData', 'The installed-application list was invalid.');
        return [];
      }
      data.forEach(function (app) {
        if (!app || typeof app.id !== 'string' || !app.id.trim()) {
          error('apps', 'InvalidData', 'Application records without a valid ID were omitted.');
          return;
        }
        var value = { id: app.id, name: text(app.name), iconPath: text(app.iconPath) };
        if (typeof app.name !== 'string' || typeof app.iconPath !== 'string') {
          error('apps', 'InvalidData', 'Missing or invalid application text fields were left empty.');
        }
        if (!byId[app.id]) byId[app.id] = { value: value, conflicts: {} };
        else merge(byId[app.id], value, ['name', 'iconPath'], 'apps');
      });
      return Object.keys(byId).sort().map(function (id) { return byId[id].value; });
    }
    function request(api, invoke, normalize) {
      var pending = true;
      var timer = global.setTimeout(function () {
        fail({ name: 'TimeoutError', message: 'The API did not respond within 8 seconds.' });
      }, 8000);
      function finish() {
        pending = false;
        global.clearTimeout(timer);
        remaining -= 1;
        if (remaining === 0) {
          discovery.result = result;
          callback(result);
        }
      }
      function fail(reason) {
        if (!pending) return;
        error(api, text(reason && reason.name).slice(0, 80) || 'UnknownError',
          text(reason && reason.message).slice(0, 240) || 'The API could not read this inventory.');
        finish();
      }
      function success(data) {
        if (!pending) return;
        try { result[api] = normalize(data); }
        catch (reason) { error(api, 'InvalidData', 'The API returned unreadable inventory data.'); }
        finish();
      }
      try { invoke(success, fail); }
      catch (reason) {
        if (!pending) throw reason;
        fail(reason);
      }
    }
    request('sources', function (success, fail) {
      if (!tv || !tv.systeminfo || typeof tv.systeminfo.getPropertyValue !== 'function') {
        fail({ name: 'NotSupportedError', message: 'The VIDEOSOURCE API is unavailable in this inspector context.' });
        return;
      }
      tv.systeminfo.getPropertyValue('VIDEOSOURCE', success, fail);
    }, readSources);
    request('apps', function (success, fail) {
      if (!tv || !tv.application || typeof tv.application.getAppsInfo !== 'function') {
        fail({ name: 'NotSupportedError', message: 'The installed-application API is unavailable in this inspector context.' });
        return;
      }
      tv.application.getAppsInfo(success, fail);
    }, readApps);
  }

  global.FourDiscovery = discovery;
  collect(function (inventory) {
    if (global.console && typeof global.console.log === 'function') {
      global.console.log(JSON.stringify(inventory, null, 2));
    }
  });
}(window));
