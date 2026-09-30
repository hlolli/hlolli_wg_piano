// Run with Bun so the shared compiler's TypeScript modules load directly.
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {gunzipSync} from 'node:zlib';

const compilerRepo = process.env.CSOUND_PLUGIN_COMPILER_REPO;
const sdk = process.env.CSOUND_PLUGIN_SDK;
if (!compilerRepo || !sdk) {
  throw new Error('Set CSOUND_PLUGIN_COMPILER_REPO and CSOUND_PLUGIN_SDK (csound-plugin-sdk.tar.gz from the host runtime build)');
}
const root = fileURLToPath(new URL('..', import.meta.url));
const {compilePlugin} = await import(pathToFileURL(resolve(compilerRepo, 'src/compiler/compile.ts')));
const {extractCsoundHeaders} = await import(pathToFileURL(resolve(compilerRepo, 'src/compiler/sdk-archive.ts')));
const headers = extractCsoundHeaders(gunzipSync(await readFile(sdk)));
const result = await compilePlugin(await readFile(resolve(root, 'hlolli_wg_piano.c'), 'utf8'), 'c', headers);
if (!result.ok) throw new Error(result.output);
const output = resolve(root, 'build/wasm/hlolli_wg_piano.wasm');
await mkdir(resolve(root, 'build/wasm'), {recursive: true});
await writeFile(output, new Uint8Array(result.wasm));
console.log(`Built ${output} (${result.wasm.byteLength} bytes)`);
