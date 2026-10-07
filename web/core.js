/* OffDayKit's independent, bounded browser adapter. No DOM, network or file APIs. */
(function (root) {
  "use strict";

  const LIMITS = Object.freeze({
    MAX_INPUT_BYTES: 10 * 1024 * 1024, MAX_DEPTH: 32, MAX_ELEMENTS: 50000,
    MAX_ATTRIBUTES: 200000, MAX_ATTRIBUTES_PER_ELEMENT: 32,
    MAX_ATTRIBUTE_BYTES: 16384, MAX_TOTAL_ATTRIBUTE_BYTES: 4 * 1024 * 1024,
    MAX_TEXT_BYTES: 2 * 1024 * 1024, MAX_NODE_TEXT_BYTES: 256 * 1024,
    MAX_INTERVALS: 10000, MAX_SELECTED_RESOURCES: 100,
    MAX_WINDOW_DAYS: 366, MAX_RECIPE_BYTES: 65536
  });
  const WEEKDAYS = Object.freeze(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]);
  const PROFILE = "ganttproject-3.4.3396-bounded-v1";
  const MAX_DIAGNOSTIC_CHARS = 512;
  // All names in the supported element/attribute allowlist are shorter than
  // this bound. Stop scanning rejected names before retaining attacker text.
  const MAX_XML_NAME_BYTES = 64;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
  const projects = new WeakMap();
  const plans = new WeakMap();
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  // Validation patterns use (?![\s\S]) as absolute end-of-input. JavaScript's
  // $ also matches before a terminal newline, which is unsafe for IDs/dates.
  const whitespace = byte => byte === 32 || byte === 9 || byte === 10 || byte === 13;
  const byteLength = value => encoder.encode(value).length;
  const names = text => new Set(text.split(" ").filter(Boolean));
  const freeze = value => {
    if (value && typeof value === "object" && !Object.isFrozen(value)) {
      for (const key of Object.keys(value)) freeze(value[key]);
      Object.freeze(value);
    }
    return value;
  };
  class OffDayKitError extends Error {
    constructor(message) {
      const text = String(message);
      super(text.length > MAX_DIAGNOSTIC_CHARS ? text.slice(0, MAX_DIAGNOSTIC_CHARS - 1) + "…" : text);
      this.name = "OffDayKitError";
    }
  }
  const fail = message => { throw new OffDayKitError(message); };
  function utf8(bytes) {
    try { return decoder.decode(bytes); }
    catch (_) { fail("Input must be strict UTF-8"); }
  }
  function bytesInput(value, maximum, label) {
    if (!(value instanceof Uint8Array)) fail(`${label} expects Uint8Array bytes`);
    if (value.byteLength > maximum) fail(`${label} exceeds its ${maximum}-byte limit`);
    // A caller's mutable buffer must never change an already validated project.
    return new Uint8Array(value);
  }
  function xmlCharacters(value) {
    for (const character of value) {
      const code = character.codePointAt(0);
      if (!(code === 9 || code === 10 || code === 13 ||
            (code >= 32 && code <= 0xD7FF) || (code >= 0xE000 && code <= 0xFFFD) ||
            (code >= 0x10000 && code <= 0x10FFFF))) fail("Invalid XML character");
    }
    return value;
  }
  function decodeXML(bytes, attribute, maximum) {
    let value = xmlCharacters(utf8(bytes)).replace(/\r\n?/g, "\n");
    if (attribute) {
      if (value.includes("<")) fail("Literal < is invalid in an XML attribute");
      value = value.replace(/[\t\n]/g, " ");
    } else if (value.includes("]]>")) fail("Unexpected CDATA terminator");
    const pieces = [];
    let position = 0, length = 0;
    function append(part) {
      length += byteLength(part);
      if (length > maximum) fail(attribute ? "XML attribute length limit exceeded" : "XML node/total text limit exceeded");
      pieces.push(part);
    }
    while (position < value.length) {
      const amp = value.indexOf("&", position);
      if (amp === -1) { append(value.slice(position)); break; }
      append(value.slice(position, amp));
      const semi = value.indexOf(";", amp + 1);
      if (semi === -1) fail("Unterminated XML character reference");
      const reference = value.slice(amp + 1, semi);
      const predefined = { amp: "&", lt: "<", gt: ">", apos: "'", quot: '"' };
      if (own(predefined, reference)) append(predefined[reference]);
      else if (/^#(?:[0-9]+|x[0-9a-fA-F]+)(?![\s\S])/.test(reference)) {
        const hex = reference[1] === "x";
        const code = Number.parseInt(reference.slice(hex ? 2 : 1), hex ? 16 : 10);
        if (!Number.isSafeInteger(code) || code > 0x10FFFF) fail("Invalid XML character reference");
        append(xmlCharacters(String.fromCodePoint(code)));
      } else fail("Custom entities and malformed references are unsupported");
      position = semi + 1;
    }
    return { value: pieces.join(""), length };
  }
  function id(value, label) {
    if (typeof value !== "string" || !/^(?:0|[1-9][0-9]{0,9})(?![\s\S])/.test(value) || Number(value) > 2147483647)
      fail(`${label} must be a canonical nonnegative 32-bit integer string`);
    return value;
  }
  function date(value, label) {
    if (typeof value !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}(?![\s\S])/.test(value)) fail(`${label} must be an ISO date YYYY-MM-DD`);
    const [year, month, day] = value.split("-").map(Number);
    if (year < 1900 || year > 2199) fail(`${label} must be in the supported planning range 1900–2199`);
    const stamp = Date.UTC(year, month - 1, day);
    const parsed = new Date(stamp);
    if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day)
      fail(`${label} is not a valid date: ${value}`);
    return stamp / 86400000;
  }
  const iso = day => new Date(day * 86400000).toISOString().slice(0, 10);
  const modulo = (a, b) => ((a % b) + b) % b;
  const weekday = day => modulo(day + 3, 7);
  const required = (attrs, keys, tag) => {
    if (keys.split(" ").some(key => !own(attrs, key))) fail(`<${tag}> is missing required attributes: ${keys}`);
  };
  const ATTRS = {
    project: "name company webLink view-date view-index gantt-divider-location resource-divider-location version locale",
    description: "", view: "zooming-state id", field: "id name width order", option: "id value", timeline: "", filters: "",
    filter: "title description is-built-in is-enabled", "simple-select": "select where", calendars: "base-id", "day-types": "", "day-type": "id",
    "default-week": "id name sun mon tue wed thu fri sat", "only-show-weekends": "value", "overriden-day-types": "", days: "", date: "year month date type color",
    tasks: "empty-milestones", taskproperties: "", taskproperty: "id name type valuetype defaultvalue",
    task: "id uid name color shape meeting project start duration complete thirdDate thirdDate-constraint priority webLink expand cost-manual-value cost-calculated fixed-start",
    notes: "", depend: "id type difference hardness", customproperty: "taskproperty-id value", resources: "",
    "custom-property-definition": "id name type default-value MSPROJECT_TYPE", resource: "id name function contacts phone", rate: "name value",
    "custom-property": "definition-id value", allocations: "", allocation: "task-id resource-id function responsible load", vacations: "",
    vacation: "start end resourceid", previous: "", "previous-tasks": "name", "previous-task": "id start duration meeting super", roles: "roleset-name", role: "id name"
  };
  const CHILDREN = {
    project: "description view calendars tasks resources allocations vacations previous roles", view: "field option timeline filters", filters: "filter", filter: "simple-select",
    calendars: "day-types date", "day-types": "day-type default-week only-show-weekends overriden-day-types days", tasks: "taskproperties task", taskproperties: "taskproperty",
    taskproperty: "simple-select", task: "task notes depend customproperty", resources: "custom-property-definition resource", resource: "rate custom-property",
    allocations: "allocation", vacations: "vacation", previous: "previous-tasks", "previous-tasks": "previous-task", roles: "role"
  };
  const SINGLETONS = {
    project: "description calendars tasks resources allocations vacations previous", view: "timeline filters", filter: "simple-select", calendars: "day-types",
    "day-types": "default-week only-show-weekends overriden-day-types days", tasks: "taskproperties", taskproperty: "simple-select", task: "notes", resource: "rate"
  };
  for (const mapping of [ATTRS, CHILDREN, SINGLETONS]) for (const key of Object.keys(mapping)) mapping[key] = names(mapping[key]);
  const TEXT_TAGS = names("description notes timeline option date");
  const BOOL_ATTRS = names("empty-milestones meeting project expand cost-calculated responsible super is-built-in is-enabled");

  function parseProject(input) {
    const source = bytesInput(input, LIMITS.MAX_INPUT_BYTES, "Project");
    if ((source[0] === 239 && source[1] === 187 && source[2] === 191) ||
        (source[0] === 255 && source[1] === 254) || (source[0] === 254 && source[1] === 255)) fail("BOMs are outside this profile; use BOM-free UTF-8");
    const stack = [], resources = [], intervals = [], references = [], customValues = [];
    const resourceIDs = new Set(), taskIDs = new Set(), taskProperties = new Map(), resourceProperties = new Map();
    let position = 0, rootSeen = false, section = null;
    let elements = 0, attributeCount = 0, attributeBytes = 0, textBytes = 0;
    const at = text => {
      for (let i = 0; i < text.length; i++) if (source[position + i] !== text.charCodeAt(i)) return false;
      return true;
    };
    function skipSpace() { const start = position; while (whitespace(source[position])) position++; return position > start; }
    function readName() {
      const start = position;
      while (position < source.length && !whitespace(source[position]) && ![47, 62, 61, 63].includes(source[position])) {
        if (position - start >= MAX_XML_NAME_BYTES) fail("XML name length limit exceeded");
        position++;
      }
      const name = utf8(source.subarray(start, position));
      if (!/^[A-Za-z_:][A-Za-z0-9_.:-]*(?![\s\S])/.test(name)) fail("Invalid or unsupported XML name");
      return name;
    }
    function findEnd(marker, start) {
      for (let i = start; i <= source.length - marker.length; i++) {
        if (source[i] !== marker.charCodeAt(0)) continue;
        let match = true;
        for (let j = 1; j < marker.length; j++) if (source[i + j] !== marker.charCodeAt(j)) { match = false; break; }
        if (match) return i;
      }
      fail("Unterminated XML markup");
    }
    function characters(value, length) {
      // XML processors do not report prolog/epilog whitespace as character data.
      if (!stack.length) { if (/[^ \t\r\n]/.test(value)) fail("Unexpected text outside project"); return; }
      textBytes += length;
      const frame = stack[stack.length - 1];
      frame.textBytes += length;
      if (textBytes > LIMITS.MAX_TEXT_BYTES || frame.textBytes > LIMITS.MAX_NODE_TEXT_BYTES) fail("XML node/total text limit exceeded");
      if (!TEXT_TAGS.has(frame.name) && /[^ \t\r\n]/.test(value)) fail(`Unexpected text inside <${frame.name}>`);
    }
    function validate(name, attrs) {
      if (!own(ATTRS, name) || Object.keys(attrs).some(key => !ATTRS[name].has(key))) fail(`Unsupported XML element or attributes: <${name}>`);
      if (stack.length) {
        const parent = stack[stack.length - 1];
        if (!own(CHILDREN, parent.name) || !CHILDREN[parent.name].has(name)) fail(`Unsupported <${name}> inside <${parent.name}>`);
        const count = (parent.children.get(name) || 0) + 1;
        parent.children.set(name, count);
        if (own(SINGLETONS, parent.name) && SINGLETONS[parent.name].has(name) && count > 1) fail(`Duplicate <${name}> section`);
      } else {
        if (name !== "project" || rootSeen) fail("Expected a single <project> root");
        rootSeen = true;
        if (attrs.version !== "3.4.3396") fail("Only the pinned GanttProject 3.4.3396 profile is supported");
      }
      for (const [key, value] of Object.entries(attrs)) if (BOOL_ATTRS.has(key) && value !== "true" && value !== "false") fail(`<${name}> ${key} must be true or false`);
      const dateKeys = name === "project" ? ["view-date"] : name === "task" ? ["start", "thirdDate"] : name === "previous-task" ? ["start"] : [];
      for (const key of dateKeys) if (own(attrs, key)) date(attrs[key], `<${name}> ${key}`);
      if (name === "task" || name === "previous-task") {
        required(attrs, "id start duration", name); id(attrs.id, `<${name}> id`); id(attrs.duration, "Task duration");
      }
      if (name === "task") {
        if (taskIDs.has(attrs.id)) fail(`Duplicate task id ${attrs.id}`);
        taskIDs.add(attrs.id);
      } else if (name === "resource") {
        required(attrs, "id name", name); id(attrs.id, "Resource id");
        if (resourceIDs.has(attrs.id)) fail(`Duplicate resource id ${attrs.id}`);
        resourceIDs.add(attrs.id); resources.push(Object.freeze({ id: attrs.id, name: attrs.name }));
      } else if (name === "vacation") {
        required(attrs, "resourceid start end", name); id(attrs.resourceid, "Vacation resourceid");
        if (date(attrs.end, "Vacation end") <= date(attrs.start, "Vacation start")) fail("Vacation exclusive end must be after start");
        if (intervals.length >= LIMITS.MAX_INTERVALS) fail("Existing interval limit exceeded");
        references.push(["resource", attrs.resourceid, "vacation"]);
      } else if (name === "allocation") {
        required(attrs, "task-id resource-id", name);
        for (const kind of ["task", "resource"]) references.push([kind, id(attrs[`${kind}-id`], `Allocation ${kind}-id`), "allocation"]);
      } else if (name === "depend") {
        required(attrs, "id", name); references.push(["task", id(attrs.id, "Dependency id"), "dependency"]);
      } else if (name === "date") {
        required(attrs, "year month date type", name);
        if (!/^[0-9]{4}(?![\s\S])/.test(attrs.year) || !/^[0-9]{1,2}(?![\s\S])/.test(attrs.month) || !/^[0-9]{1,2}(?![\s\S])/.test(attrs.date)) fail("Only explicit, finite calendar dates are supported");
        date(`${attrs.year}-${attrs.month.padStart(2, "0")}-${attrs.date.padStart(2, "0")}`, "Calendar date");
      } else if (name === "taskproperty" || name === "custom-property-definition") {
        required(attrs, "id", name);
        const taskProperty = name === "taskproperty";
        const definitions = taskProperty ? taskProperties : resourceProperties;
        if (definitions.has(attrs.id)) fail(`Duplicate ${name} id`);
        const type = attrs[taskProperty ? "valuetype" : "type"] || "";
        const defaultValue = attrs[taskProperty ? "defaultvalue" : "default-value"];
        if (defaultValue && type === "date") date(defaultValue, "Custom date default");
        definitions.set(attrs.id, type);
      } else if (name === "customproperty" || name === "custom-property") {
        const key = name === "customproperty" ? "taskproperty-id" : "definition-id";
        required(attrs, key, name); customValues.push([name, attrs[key], attrs.value || ""]);
      }
    }
    function finish(frame, closeStart, end) {
      if (frame.name === "vacation") intervals.push({ resource_id: frame.attrs.resourceid, start: frame.attrs.start, end_exclusive: frame.attrs.end, rawStart: frame.start, rawEnd: end });
      else if (frame.name === "vacations") section = { start: frame.start, openEnd: frame.openEnd, closeStart, end, selfClosing: frame.selfClosing };
      else if (frame.name === "project") for (const key of ["tasks", "resources", "vacations"]) if (frame.children.get(key) !== 1) fail(`Exactly one <${key}> section is required`);
    }
    while (position < source.length) {
      if (source[position] !== 60) {
        const start = position;
        while (position < source.length && source[position] !== 60) position++;
        // References are illegal outside the root, including whitespace references.
        const raw = source.subarray(start, position);
        if (!stack.length) {
          const value = xmlCharacters(utf8(raw));
          if (/[^ \t\r\n]/.test(value)) fail("Unexpected text outside project");
        } else {
          const frame = stack[stack.length - 1];
          const decoded = decodeXML(raw, false, Math.min(LIMITS.MAX_NODE_TEXT_BYTES - frame.textBytes, LIMITS.MAX_TEXT_BYTES - textBytes));
          characters(decoded.value, decoded.length);
        }
      } else if (at("<!--")) {
        const end = findEnd("-->", position + 4);
        const value = xmlCharacters(utf8(source.subarray(position + 4, end))).replace(/\r\n?/g, "\n");
        if (value.includes("--") || value.endsWith("-")) fail("Invalid XML comment");
        const size = byteLength(value); textBytes += size;
        if (size > LIMITS.MAX_NODE_TEXT_BYTES || textBytes > LIMITS.MAX_TEXT_BYTES) fail("XML comment/text limit exceeded");
        if (stack.some(frame => frame.name === "vacations")) fail("Comments inside vacations are outside the supported profile");
        position = end + 3;
      } else if (at("<![CDATA[")) {
        if (!stack.length || !TEXT_TAGS.has(stack[stack.length - 1].name)) fail("CDATA is allowed only in documented text elements");
        const end = findEnd("]]>", position + 9);
        const value = xmlCharacters(utf8(source.subarray(position + 9, end))).replace(/\r\n?/g, "\n");
        characters(value, byteLength(value)); position = end + 3;
      } else if (at("<?")) {
        if (position !== 0 || !at("<?xml")) fail("Processing instructions are unsupported");
        const end = findEnd("?>", position + 2);
        const declaration = xmlCharacters(utf8(source.subarray(position, end + 2)));
        const match = /^<\?xml[ \t\r\n]+version[ \t\r\n]*=[ \t\r\n]*(["'])1\.0\1(?:[ \t\r\n]+encoding[ \t\r\n]*=[ \t\r\n]*(["'])([A-Za-z][A-Za-z0-9._-]*)\2)?(?:[ \t\r\n]+standalone[ \t\r\n]*=[ \t\r\n]*(["'])(?:yes|no)\4)?[ \t\r\n]*\?>$/.exec(declaration);
        if (!match || (match[3] && match[3].toUpperCase() !== "UTF-8")) fail("Only XML 1.0 with UTF-8 encoding is supported");
        position = end + 2;
      } else if (at("<!")) fail("DTD, declarations and custom entities are unsupported");
      else if (at("</")) {
        const closeStart = position; position += 2;
        const name = readName(); skipSpace();
        if (source[position++] !== 62) fail("Malformed XML closing tag");
        const frame = stack.pop();
        if (!frame || frame.name !== name) fail("Mismatched XML closing tag");
        finish(frame, closeStart, position);
      } else {
        const start = position++; const name = readName();
        if (++elements > LIMITS.MAX_ELEMENTS || stack.length >= LIMITS.MAX_DEPTH) fail("XML element/depth limit exceeded");
        const attrs = Object.create(null); let count = 0, selfClosing = false;
        while (true) {
          const separated = skipSpace();
          if (source[position] === 62) { position++; break; }
          if (source[position] === 47 && source[position + 1] === 62) { position += 2; selfClosing = true; break; }
          if (!separated || position >= source.length) fail("Malformed XML opening tag");
          const key = readName();
          if (own(attrs, key)) fail("Duplicate XML attribute");
          if (++count > LIMITS.MAX_ATTRIBUTES_PER_ELEMENT || ++attributeCount > LIMITS.MAX_ATTRIBUTES) fail("XML attribute-count limit exceeded");
          skipSpace(); if (source[position++] !== 61) fail("Expected = after XML attribute name");
          skipSpace(); const quote = source[position++];
          if (quote !== 34 && quote !== 39) fail("XML attributes must be quoted");
          const valueStart = position;
          while (position < source.length && source[position] !== quote) position++;
          if (position === source.length) fail("Unterminated XML attribute");
          const keyLength = byteLength(key);
          if (keyLength > LIMITS.MAX_ATTRIBUTE_BYTES) fail("XML attribute length limit exceeded");
          const decoded = decodeXML(source.subarray(valueStart, position++), true, LIMITS.MAX_ATTRIBUTE_BYTES - keyLength);
          attributeBytes += keyLength + decoded.length;
          if (attributeBytes > LIMITS.MAX_TOTAL_ATTRIBUTE_BYTES) fail("XML total attribute length limit exceeded");
          attrs[key] = decoded.value;
        }
        validate(name, attrs);
        const frame = { name, attrs, start, openEnd: position, selfClosing, children: new Map(), textBytes: 0 };
        if (selfClosing) finish(frame, position, position); else stack.push(frame);
      }
    }
    if (stack.length || !rootSeen || !section) fail("Incomplete XML project or missing vacations section");
    for (const [kind, target, origin] of references) if (!(kind === "task" ? taskIDs : resourceIDs).has(target)) fail(`Dangling ${origin} reference to ${kind} ${target}`);
    for (const [kind, key, value] of customValues) {
      const definitions = kind === "customproperty" ? taskProperties : resourceProperties;
      if (!definitions.has(key)) fail(`Dangling ${kind} definition ${key}`);
      if (value && definitions.get(key) === "date") date(value, "Custom date value");
    }
    const publicIntervals = intervals.map(interval => Object.freeze({
      ...intervalRecord(interval), get raw() { return source.slice(interval.rawStart, interval.rawEnd); }
    }));
    const project = Object.freeze({
      resources: Object.freeze(resources), intervals: Object.freeze(publicIntervals), byteLength: source.length,
      vacation_start: section.start, vacation_open_end: section.openEnd,
      vacation_close_start: section.closeStart, vacation_end: section.end, self_closing: section.selfClosing,
      get source() { return source.slice(); }
    });
    projects.set(project, { source, resources, intervals, section, hash: null });
    return project;
  }

  // JSON.parse cannot detect duplicate keys or distinguish 1 from 1.0. This
  // bounded reader preserves that distinction before validating the six fields.
  function recipeJSON(text) {
    let position = 0;
    const floatToken = Symbol("non-integer JSON token");
    const space = () => { while (/[ \t\r\n]/.test(text[position] || "x")) position++; };
    function string() {
      const start = position++;
      while (position < text.length) {
        const c = text[position++];
        if (c === '"') {
          try { return JSON.parse(text.slice(start, position)); } catch (_) { fail("Malformed JSON string"); }
        }
        if (c === "\\") position++;
      }
      fail("Unterminated JSON string");
    }
    function value(depth) {
      if (depth > 64) fail("Recipe JSON nesting is unsupported");
      space(); const character = text[position];
      if (character === '"') return string();
      if (character === "{" || character === "[") {
        const object = character === "{"; const result = object ? Object.create(null) : [];
        const end = object ? "}" : "]"; position++; space();
        if (text[position] === end) { position++; return result; }
        while (true) {
          space(); let key;
          if (object) {
            if (text[position] !== '"') fail("Recipe JSON keys must be strings");
            key = string(); if (own(result, key)) fail(`Duplicate recipe key: ${key}`);
            space(); if (text[position++] !== ":") fail("Malformed recipe JSON object");
          }
          const next = value(depth + 1);
          if (object) result[key] = next; else result.push(next);
          space(); const delimiter = text[position++];
          if (delimiter === end) return result;
          if (delimiter !== ",") fail("Malformed recipe JSON collection");
        }
      }
      for (const [token, result] of [["true", true], ["false", false], ["null", null]]) {
        if (text.startsWith(token, position)) { position += token.length; return result; }
      }
      const number = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(position));
      if (!number) fail("Recipe must be bounded UTF-8 JSON with finite numbers");
      position += number[0].length;
      if (/[.eE]/.test(number[0])) return floatToken;
      const parsed = Number(number[0]);
      if (!Number.isSafeInteger(parsed)) fail("Recipe JSON integer is out of range");
      return parsed;
    }
    const result = value(0); space();
    if (position !== text.length) fail("Unexpected content after recipe JSON");
    return result;
  }
  function parseRecipe(input) {
    let object = input;
    if (typeof input === "string" || input instanceof Uint8Array) {
      const bytes = typeof input === "string" ? encoder.encode(input) : input;
      if (bytes.length > LIMITS.MAX_RECIPE_BYTES) fail("Recipe exceeds the 64 KiB input limit");
      object = recipeJSON(utf8(bytes));
    }
    const expected = ["weekdays", "every_weeks", "anchor", "start", "end", "exclusions"];
    if (!object || typeof object !== "object" || Array.isArray(object) ||
        Reflect.ownKeys(object).length !== expected.length || expected.some(key => !own(object, key)))
      fail("Recipe must have exactly weekdays, every_weeks, anchor, start, end, exclusions; resource IDs are never stored in recipes");
    if (expected.some(key => !own(Object.getOwnPropertyDescriptor(object, key), "value"))) fail("Recipe fields must be data values");
    const days = object.weekdays, exclusions = object.exclusions;
    if (!Array.isArray(days) || !days.length || days.length > 7 || [...days].some(day => typeof day !== "string" || !WEEKDAYS.includes(day)) || new Set(days).size !== days.length)
      fail("Choose one to seven unique lowercase English weekdays");
    if (!Number.isInteger(object.every_weeks) || ![1, 2].includes(object.every_weeks)) fail("every_weeks must be integer 1 or 2");
    const anchor = date(object.anchor, "Recipe anchor"), start = date(object.start, "Recipe start"), end = date(object.end, "Recipe end");
    if (weekday(anchor) !== 0) fail("Recipe anchor must be a Monday");
    if (end - start + 1 < 1 || end - start + 1 > LIMITS.MAX_WINDOW_DAYS) fail("The inclusive window must contain 1 to 366 days");
    if (object.end === "2199-12-31") fail("The final supported window date is 2199-12-30");
    if (!Array.isArray(exclusions) || exclusions.length > LIMITS.MAX_WINDOW_DAYS || new Set(exclusions).size !== exclusions.length) fail("exclusions must contain at most 366 unique dates");
    for (const value of exclusions) {
      const day = date(value, "Exclusion");
      if (day < start || day > end) fail("Every exclusion must be inside the inclusive window");
    }
    return freeze({ weekdays: [...days].sort((a, b) => WEEKDAYS.indexOf(a) - WEEKDAYS.indexOf(b)), every_weeks: object.every_weeks,
      anchor: object.anchor, start: object.start, end: object.end, exclusions: [...exclusions].sort() });
  }
  function candidateDates(recipe) {
    const result = [], anchor = date(recipe.anchor, "Recipe anchor"), end = date(recipe.end, "Recipe end");
    const wanted = new Set(recipe.weekdays.map(day => WEEKDAYS.indexOf(day)));
    for (let day = date(recipe.start, "Recipe start"); day <= end; day++)
      if (wanted.has(weekday(day)) && modulo(Math.floor((day - anchor) / 7), recipe.every_weeks) === 0) result.push(iso(day));
    return result;
  }
  function getProject(project) {
    const stored = projects.get(project);
    if (!stored) fail("Use a project returned by parseProject");
    return stored;
  }
  function intervalRecord(interval) {
    return { resource_id: interval.resource_id, start: interval.start, end_exclusive: interval.end_exclusive };
  }
  async function sha256(input) {
    if (!(input instanceof Uint8Array)) fail("sha256 expects Uint8Array bytes");
    if (!root.crypto || !root.crypto.subtle) fail("Web Crypto SHA-256 is unavailable in this browser");
    const digest = await root.crypto.subtle.digest("SHA-256", new Uint8Array(input));
    return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
  }
  function projectHash(stored) {
    if (!stored.hash) stored.hash = sha256(stored.source);
    return stored.hash;
  }
  async function inventory(project) {
    const stored = getProject(project), byResource = new Map(stored.resources.map(resource => [resource.id, []]));
    for (const interval of stored.intervals) byResource.get(interval.resource_id).push(intervalRecord(interval));
    return freeze({ profile: PROFILE, source_sha256: await projectHash(stored),
      resources: stored.resources.map(resource => ({ ...resource, existing_intervals: byResource.get(resource.id) })), existing_interval_count: stored.intervals.length });
  }
  function render(stored, additions) {
    if (!additions.length) return stored.source;
    const { source, section } = stored;
    const records = additions.map(interval => `\n        <vacation start="${interval.start}" end="${interval.end_exclusive}" resourceid="${interval.resource_id}"/>`).join("");
    const insert = encoder.encode((section.selfClosing ? ">" : "") + records + "\n    " + (section.selfClosing ? "</vacations>" : ""));
    const before = section.selfClosing ? section.openEnd - 2 : section.closeStart;
    const after = section.selfClosing ? section.end : section.closeStart;
    const size = before + insert.length + source.length - after;
    if (size > LIMITS.MAX_INPUT_BYTES) fail("Generated output would exceed the 10 MiB supported-project limit");
    const output = new Uint8Array(size);
    output.set(source.subarray(0, before)); output.set(insert, before); output.set(source.subarray(after), before + insert.length);
    return output;
  }
  async function preview(project, recipeInput, selectedIDs = []) {
    const stored = getProject(project), recipe = parseRecipe(recipeInput), selected = [];
    if (selectedIDs == null || typeof selectedIDs === "string" || typeof selectedIDs[Symbol.iterator] !== "function") fail("Selected resource IDs must be a bounded iterable of strings");
    for (const value of selectedIDs) {
      if (selected.length >= LIMITS.MAX_SELECTED_RESOURCES) fail("At most 100 resources may be selected");
      selected.push(id(value, "Selected resource id"));
    }
    if (new Set(selected).size !== selected.length) fail("A resource may be selected only once");
    const known = new Set(stored.resources.map(resource => resource.id));
    if (selected.some(value => !known.has(value))) fail("Every selected resource must already exist in this project");
    selected.sort((a, b) => Number(a) - Number(b));
    const dates = candidateDates(recipe), excluded = new Set(recipe.exclusions), candidates = [], additions = [];
    for (const resourceID of selected) {
      const existing = stored.intervals.filter(interval => interval.resource_id === resourceID);
      for (const day of dates) {
        let first = null, count = 0;
        for (const interval of existing) if (interval.start <= day && day < interval.end_exclusive) { if (!first) first = interval; count++; }
        const isExcluded = excluded.has(day), status = isExcluded ? "excluded" : first ? "covered" : "add";
        candidates.push({ resource_id: resourceID, date: day, excluded: isExcluded, covered: first !== null,
          status, covering_interval_count: count, covering_interval_example: first ? intervalRecord(first) : null });
        if (status === "add") {
          if (stored.intervals.length + additions.length >= LIMITS.MAX_INTERVALS) fail("Existing plus generated intervals would exceed 10000");
          additions.push({ resource_id: resourceID, start: day, end_exclusive: iso(date(day, "Candidate date") + 1) });
        }
      }
    }
    const output = render(stored, additions);
    if (additions.length) parseProject(output); // Generated records share every input bound.
    const [sourceHash, outputHash] = await Promise.all([projectHash(stored), additions.length ? sha256(output) : projectHash(stored)]);
    const receipt = freeze({ format: "off-day-kit-receipt-v1", profile: PROFILE,
      purpose: "Prepare native days-off records; no scheduling or workload guarantees", recipe,
      selected_resource_ids: selected, candidate_dates: dates.map(day => ({ date: day, excluded: excluded.has(day) })),
      candidates_by_resource: candidates, additions, addition_count: additions.length,
      existing_interval_count: stored.intervals.length, output_interval_count: stored.intervals.length + additions.length,
      source_sha256: sourceHash, output_sha256: outputHash, no_op: additions.length === 0 });
    plans.set(receipt, { source: stored.source, output });
    return receipt;
  }
  function apply(project, receipt) {
    const stored = getProject(project), plan = plans.get(receipt);
    if (!plan) fail("Plan has changed or is not an authentic preview; create a fresh preview");
    if (!receipt.selected_resource_ids.length) fail("Applying requires explicit resource IDs for this project");
    if (stored.source.length !== plan.source.length || stored.source.some((byte, index) => byte !== plan.source[index])) fail("Plan belongs to a different source project");
    // Receipts and their nested values are frozen; source and output are private.
    return plan.output.slice();
  }
  root.OffDayCore = Object.freeze({ OffDayKitError, LIMITS, WEEKDAYS, parseProject, parseRecipe, inventory, preview, apply, sha256 });
})(globalThis);
