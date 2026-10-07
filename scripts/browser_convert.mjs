import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {openApp,loadNative,pattern,saveDownload,E,INPUT} from './browser_common.mjs';
const app=await openApp(),{page}=app,downloads=[];
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
try{
 await loadNative(page);await pattern(page);assert.equal(await page.locator('#addition-count').textContent(),'5');await page.locator('#ack').check();
 downloads.push(await saveDownload(page,'#download','generated.gan'));downloads.push(await saveDownload(page,'#report','generated-receipt.json'));downloads.push(await saveDownload(page,'#recipe','browser-recipe.json'));downloads.push(await saveDownload(page,'#download','browser-repeated.gan'));
 assert.deepEqual(await fs.readFile(path.join(E,'generated.gan')),await fs.readFile(path.join(E,'browser-repeated.gan')));
 await loadNative(page,path.join(E,'generated.gan'));assert.equal(await page.locator('input[data-resource-id]:checked').count(),0);await pattern(page);assert.equal(await page.locator('#addition-count').textContent(),'0');await page.locator('#ack').check();downloads.push(await saveDownload(page,'#download','browser-noop.gan'));downloads.push(await saveDownload(page,'#report','browser-noop-receipt.json'));
 assert.deepEqual(await fs.readFile(path.join(E,'generated.gan')),await fs.readFile(path.join(E,'browser-noop.gan')));
 await loadNative(page);await pattern(page,'2027-01-11');await page.locator('#ack').check();downloads.push(await saveDownload(page,'#download','browser-negative-shifted-anchor.gan'));downloads.push(await saveDownload(page,'#report','browser-negative-shifted-anchor-receipt.json'));
 assert.deepEqual(app.errors,[]);assert.deepEqual(app.network,[]);
 const records=[];for(const item of downloads)records.push({...item,path:path.basename(item.path),sha256:sha(await fs.readFile(item.path))});
 await fs.writeFile(path.join(E,'browser-production-result.json'),JSON.stringify({status:'pass',sourceSha256:sha(await fs.readFile(INPUT)),actualFileProtocolDownloads:true,explicitResourceIds:['0','1'],repeatByteIdentical:true,reappliedByteIdentical:true,downloads:records,consoleErrors:app.errors,networkRequests:app.network},null,2)+'\n');
}catch(error){await page.screenshot({path:path.join(E,'FAILED-browser-convert.png'),fullPage:true});throw error;}finally{await app.browser.close();}
