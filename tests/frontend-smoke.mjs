// DOM-double unit checks. These are not a substitute for browser/layout QA.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
class Element {
  constructor() { this.children=[]; this.dataset={}; this.style={}; this.attrs={}; this.value=''; this.disabled=false; this.checked=false; this.hidden=false; this.listeners={}; const items=new Set(); this.classList={add:(v)=>items.add(v),contains:(v)=>items.has(v),toggle:(v,on)=>{const next=on??!items.has(v); if(next)items.add(v);else items.delete(v);return next;}}; }
  setAttribute(k,v){this.attrs[k]=v;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  addEventListener(k,fn){this.listeners[k]=fn;}
  showModal(){this.open=true;} close(){this.open=false;}
}
const html=fs.readFileSync('public/index.html','utf8');
const ids=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element()]));
const directions=['long','short'].map(d=>{const e=new Element();e.dataset.direction=d;return e;});
const document={getElementById(id){assert.ok(ids.has(id),`Missing HTML id ${id}`);return ids.get(id);},createElement:()=>new Element(),createElementNS:()=>new Element(),body:new Element(),querySelectorAll(selector){if(selector==='[data-direction]')return directions;if(selector==='[data-horizon]')return [...ids.get('horizon-labels').children,...ids.get('time-table').children];return [];}};
const snapshot=JSON.parse(fs.readFileSync('public/data/snapshot.json','utf8'));
const context=vm.createContext({document,console,URL,Intl,Date,Number,Math,localStorage:{getItem:()=>null,setItem(){}},fetch:async()=>({ok:true,json:async()=>structuredClone(snapshot)})});
vm.runInContext(fs.readFileSync('public/app.js','utf8'),context);
await new Promise(resolve=>setImmediate(resolve));
assert.equal(ids.get('calculate').disabled,false);
assert.match(String(ids.get('touch-value').textContent),/^\d+$/);
const initial=ids.get('touch-value').textContent;
vm.runInContext('calculate()',context);assert.equal(ids.get('touch-value').textContent,initial);
vm.runInContext('setHorizon(9)',context);assert.equal(ids.get('horizon').value,9);
vm.runInContext("chooseDirection('short'); calculate()",context);
assert.equal(ids.get('form-message').hidden,true);
ids.get('stop').value=String(snapshot.levels.find(v=>v>snapshot.referencePrice));
vm.runInContext('calculate()',context);assert.match(ids.get('before-stop-value').textContent,/^\d+%$/);
ids.get('target').value='-1';vm.runInContext('calculate()',context);assert.equal(ids.get('form-message').hidden,false);
assert.match(ids.get('form-message').textContent,/positive price/);
vm.runInContext('setTheme(true)',context);assert.equal(document.body.classList.contains('dark'),true);
assert.throws(()=>vm.runInContext('validateSnapshot({schemaVersion:9})',context),/Unsupported/);
assert.ok(ids.get('scenario-chart').children.length>5);
assert.ok(ids.get('source-details').children.length>0);
console.log('Frontend smoke checks passed: snapshot load, repeated calculation, horizons, short/stop, validation, theme, charts, source context.');
