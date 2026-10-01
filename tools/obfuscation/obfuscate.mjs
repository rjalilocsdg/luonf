import fs from 'node:fs';
import path from 'node:path';
import Obfuscator from 'javascript-obfuscator';

const root = process.argv[2];
if (!root) throw new Error('Usage: node obfuscate.mjs <staging directory>');
function protect(source) {
  const placeholders = [];
  source = source.replace(/@@[A-Z_]+@@/g, token => {
    const name = `__LUNEL_TEMPLATE_${placeholders.length}__`;
    placeholders.push([name, token]);
    return name;
  });
  let result = Obfuscator.obfuscate(source, {
    target: 'browser', compact: true, simplify: true,
    identifierNamesGenerator: 'hexadecimal', renameGlobals: false,
    reservedNames: ['^__LUNEL_TEMPLATE_'],
    renameProperties: false, controlFlowFlattening: true,
    controlFlowFlatteningThreshold: 1, deadCodeInjection: true,
    deadCodeInjectionThreshold: 0.4, numbersToExpressions: true,
    splitStrings: true, splitStringsChunkLength: 5,
    stringArray: true, stringArrayThreshold: 1,
    stringArrayEncoding: ['rc4'], stringArrayRotate: true,
    stringArrayShuffle: true, stringArrayWrappersCount: 5,
    stringArrayWrappersChainedCalls: true,
    stringArrayWrappersType: 'function', stringArrayCallsTransform: true,
    stringArrayCallsTransformThreshold: 1, transformObjectKeys: true,
    unicodeEscapeSequence: true, sourceMap: false,
    // Anti-debug loops and self-defending code can hang legitimate browsers.
    debugProtection: false, selfDefending: false,
  }).getObfuscatedCode();
  for (const [name, token] of placeholders) result = result.replaceAll(name, token);
  return result;
}
function html(source) {
  return source.replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script\s*>)/gi,
    (all, open, code, close) => {
      if (/\bsrc\s*=|\btype\s*=\s*["'](?:importmap|application\/[^"']+)["']/i.test(open) || !code.trim()) return all;
      return open + protect(code).replace(/<\/script/gi, '<\\/script') + close;
    });
}
function walk(dir) {
  for (const item of fs.readdirSync(dir, {withFileTypes: true})) {
    const file = path.join(dir, item.name);
    if (item.isDirectory()) walk(file);
    else if (file.endsWith('.js')) fs.writeFileSync(file, protect(fs.readFileSync(file, 'utf8')));
    else if (file.endsWith('.html')) fs.writeFileSync(file, html(fs.readFileSync(file, 'utf8')));
    else if (item.name === 'panel.py') {
      const source = fs.readFileSync(file, 'utf8');
      const match = /PAGE\s*=\s*r?"""([\s\S]*?)"""/.exec(source);
      if (!match) throw new Error(`Cannot locate PAGE in ${file}`);
      // JSON string syntax is valid Python here; retain literal backslashes.
      const literal = JSON.stringify(html(match[1]));
      fs.writeFileSync(file, source.slice(0, match.index) + 'PAGE = ' + literal + source.slice(match.index + match[0].length));
    }
  }
}
walk(root);
