/* Termius 简体中文补丁 — 运行时界面翻译层
 * 只处理界面文本与表单提示，不触碰终端输出、输入框内容与业务逻辑。
 * 词典由 生成补丁.py 注入，可编辑 词典.json 后重新生成。
 */
(function () {
  'use strict';

  var DICT = __DICT_JSON__;
  var DICT_CI = __DICT_CI_JSON__;
  var PREFIX = __PREFIX_JSON__;
  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt', 'label'];
  // 终端内容、代码、可编辑区域一律跳过，避免误翻译远程主机输出
  var SKIP = 'script,style,noscript,textarea,code,pre,svg,canvas,' +
             '.xterm-rows,.xterm-screen,.xterm,.monaco-editor,' +
             '[contenteditable="true"],[data-zh-skip]';
  var textCache = new WeakMap();
  var attrCache = new WeakMap();

  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  function lookup(raw) {
    var t = norm(raw);
    if (!t) return null;
    if (Object.prototype.hasOwnProperty.call(DICT, t)) return DICT[t];

    // 去掉尾部标点后再查，标点原样保留
    var m = t.match(/^(.*?)([:.!?\u2026\u3002\uff01\uff1f\uff1a]+)$/);
    if (m) {
      var base = m[1];
      if (Object.prototype.hasOwnProperty.call(DICT, base)) return DICT[base] + m[2];
      if (Object.prototype.hasOwnProperty.call(DICT_CI, base.toLowerCase())) return DICT_CI[base.toLowerCase()] + m[2];
    }
    if (Object.prototype.hasOwnProperty.call(DICT_CI, t.toLowerCase())) return DICT_CI[t.toLowerCase()];

    // 组合短语，例如 "Continue with Google"
    for (var i = 0; i < PREFIX.length; i++) {
      var p = PREFIX[i][0];
      if (t.indexOf(p) === 0 && t.length > p.length) {
        var rest = t.slice(p.length);
        return PREFIX[i][1] + (rest.charAt(0) === ' ' ? '' : ' ') + rest;
      }
    }
    return null;
  }

  function isSkipped(el) {
    return !!(el && el.nodeType === 1 && el.closest && el.closest(SKIP));
  }

  function translateText(node) {
    var raw = node.nodeValue;
    if (textCache.get(node) === raw) return;
    var zh = lookup(raw);
    if (zh === null) { textCache.set(node, raw); return; }
    var lead = (raw.match(/^\s*/) || [''])[0];
    var tail = (raw.match(/\s*$/) || [''])[0];
    var out = lead + zh + tail;
    if (out !== raw) node.nodeValue = out;
    textCache.set(node, out);
  }

  function translateAttrs(el) {
    if (isSkipped(el)) return;
    var cache = attrCache.get(el) || {};
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute || !el.hasAttribute(a)) continue;
      var v = el.getAttribute(a);
      if (cache[a] === v) continue;
      var zh = lookup(v);
      cache[a] = (zh === null) ? v : zh;
      if (zh !== null) el.setAttribute(a, zh);
    }
    if (el.tagName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type || '')) {
      var val = el.getAttribute('value');
      if (val !== null && cache['value'] !== val) {
        var zv = lookup(val);
        cache['value'] = (zv === null) ? val : zv;
        if (zv !== null) el.setAttribute('value', zv);
      }
    }
    attrCache.set(el, cache);
  }

  function walk(root) {
    if (!root) return;
    var filter = {
      acceptNode: function (n) {
        if (n.nodeType === 1 && isSkipped(n)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    };
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, filter, false);
    var n;
    while ((n = walker.nextNode())) {
      if (n.nodeType === 3) {
        if (!isSkipped(n.parentElement)) translateText(n);
      } else if (n.nodeType === 1) {
        translateAttrs(n);
      }
    }
  }

  var timer = null;
  function schedule() {
    if (timer) return;
    timer = setTimeout(function () {
      timer = null;
      walk(document.body);
      if (document.title) {
        var t = lookup(document.title);
        if (t) document.title = t;
      }
    }, 60);
  }

  try {
    var obs = new MutationObserver(schedule);
    obs.observe(document.documentElement, {
      subtree: true, childList: true, characterData: true,
      attributes: true, attributeFilter: ATTRS.concat(['value'])
    });
  } catch (e) { /* 老环境退化：仍做一次性翻译 */ }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { walk(document.body); });
  }
  walk(document.body);
  schedule();
})();
