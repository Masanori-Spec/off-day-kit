import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright';
export const E=path.resolve('evidence'),INPUT=path.join(E,'gui-authored.gan');
export async function openApp(){
 const browser=await chromium.launch({chromiumSandbox:true});
 try{
  const commands=execFileSync('ps',['-eo','pid=,ppid=,args='],{encoding:'utf8'}).split('\n').filter(line=>{const m=line.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/);return m&&Number(m[2])===process.pid&&/chrome(?:-headless-shell)?(?:\s|$)/.test(m[3]);});
  assert.equal(commands.length,1);assert.ok(!commands[0].includes('--no-sandbox')&&!commands[0].includes('--disable-setuid-sandbox'));
  let records=[];try{records=JSON.parse(await fs.readFile(path.join(E,'browser-launches.json'),'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;}
  records.push({script:path.basename(process.argv[1]),chromiumSandbox:true,command:commands[0].trim()});await fs.writeFile(path.join(E,'browser-launches.json'),JSON.stringify(records,null,2)+'\n');
 }catch(error){await browser.close();throw error;}
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});await context.setOffline(true);const page=await context.newPage();page.setDefaultTimeout(10000);
 const errors=[],network=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 await page.goto(pathToFileURL(path.join(E,'offline-app/index.html')).href);await page.locator('#choose-file').waitFor();return {browser,context,page,errors,network};
}
export async function state(page,value){await page.waitForFunction(v=>document.body.dataset.state===v,value);}
export async function loadNative(page,input=INPUT){await page.locator('#file-input').setInputFiles(input);await state(page,'loaded');}
export async function pattern(page,anchor='2027-01-04'){
 await page.locator('#cadence').selectOption('2');await page.locator('#anchor').fill(anchor);await page.locator('#start').fill('2027-01-04');await page.locator('#end').fill('2027-02-28');await page.locator('#exclusions').fill('2027-01-22');
 for(const day of ['monday','tuesday','wednesday','thursday','saturday','sunday'])await page.locator('#weekday-'+day).uncheck();await page.locator('#weekday-friday').check();
 for(const id of ['0','1'])await page.locator(`input[data-resource-id="${id}"]`).check();await page.locator('#preview').click();await state(page,'ready');
}
export async function saveDownload(page,button,name){
 const dest=path.join(E,name);await assert.rejects(fs.stat(dest),{code:'ENOENT'});const pending=page.waitForEvent('download');await page.locator(button).click();const d=await pending;await d.saveAs(dest);assert.ok((await fs.stat(dest)).size>0);return {path:dest,suggestedFilename:d.suggestedFilename()};
}
export async function dropText(page,text,name='synthetic.gan'){
 await page.evaluate(({text,name})=>{const d=new DataTransfer();d.items.add(new File([text],name,{type:'application/xml'}));document.getElementById('drop-zone').dispatchEvent(new DragEvent('drop',{dataTransfer:d,bubbles:true}));},{text,name});
}
