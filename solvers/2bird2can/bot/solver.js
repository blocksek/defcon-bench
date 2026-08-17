const puppeteer=require('puppeteer-core');const fs=require('fs');
const CHROME=process.env.CHROME_BIN||"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const CLIENT_URL=process.env.CLIENT_URL||"http://localhost:3000/";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const N=parseInt(process.env.N||"4");
const FX=parseFloat(process.env.FX),FY=parseFloat(process.env.FY);
function log(...a){console.log(new Date().toISOString().slice(11,19),...a);}
const hookSrc=fs.readFileSync('hook.js','utf8')+`
;window.__reads=function(){var f=window.__lastIn;var out=[];if(f&&f.length){for(var k=Math.max(0,f.length-60);k<f.length;k++){var b=f[k];if(b.byteLength<63)continue;var dv=new DataView(b.buffer,b.byteOffset,b.byteLength);var x=dv.getFloat32(55,true),y=dv.getFloat32(59,true);if(isFinite(x)&&isFinite(y)&&Math.abs(x)<3e5&&Math.abs(y)<3e5)out.push([x,y]);}}return {r:out,flag:window.__flag,ws:(window.__wsList.length?window.__wsList[window.__wsList.length-1].readyState:3)};};`;
async function join(page){
  await page.goto(CLIENT_URL,{waitUntil:'domcontentloaded',timeout:60000});
  await sleep(9000);
  let ws=0;for(let a=0;a<10&&ws===0;a++){await page.mouse.click(765,580);await sleep(1000);ws=await page.evaluate(()=>window.__wsList.length);}
  await sleep(1500);await page.mouse.click(480,300);page.__keys=new Set();return ws;
}
async function newClient(browser){
  const page=await browser.newPage();await page.setViewport({width:1000,height:700});
  await page.evaluateOnNewDocument(hookSrc);
  const ws=await join(page);return page;
}
async function press(page,keys){ // force fresh keydown of desired set, release others
  for(const k of ['KeyA','KeyD','KeyW','KeyS']){ if(!keys.has(k)) await page.keyboard.up(k).catch(()=>{}); }
  for(const k of keys){ await page.keyboard.down(k).catch(()=>{}); }
  page.__keys=new Set(keys);
}
function dirKeys(dx,dy,tol){const s=new Set();if(dx>tol)s.add('KeyD');else if(dx<-tol)s.add('KeyA');if(dy>tol)s.add('KeyW');else if(dy<-tol)s.add('KeyS');return s;}
const fdir=[Math.sign(FX),Math.sign(FY)]; // flight quadrant sign
function progress(p){ return p[0]*fdir[0]+p[1]*fdir[1]; } // how far toward flag quadrant
(async()=>{
  log("target",FX,FY,"dist",Math.hypot(FX,FY).toFixed(0),"N",N,"fdir",fdir);
  const browser=await puppeteer.launch({executablePath:CHROME,headless:"new",userDataDir:"/tmp/twobird-prof/run4",args:["--no-sandbox","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist","--window-size=1020,720","--disable-background-timer-throttling","--disable-backgrounding-occluded-windows","--disable-renderer-backgrounding","--disable-features=CalculateNativeWinOcclusion"]});
  const pages=[];
  for(let i=0;i<N;i++){const p=await newClient(browser);const ws=await p.evaluate(()=>window.__wsList.length);pages.push(p);log("client",i,"ws",ws);}
  log("all joined; flying");
  let pos=[0,0],flag=null,t0=Date.now(),step=0,bestProg=-1e9,stallSteps=0,wiggle=0;
  while(true){
    step++;const now=Date.now();
    // gather reads from all clients, pick frontier (max progress toward flag), ignore origin stragglers
    let all=[];let dead=[];
    for(let i=0;i<pages.length;i++){ try{const o=await pages[i].evaluate(()=>window.__reads());for(const p of o.r)all.push(p);if(o.flag&&!flag)flag=o.flag;if(o.ws===3)dead.push(i);}catch(e){} }
    if(all.length){
      // frontier = read with max progress; but robust: take 90th percentile progress point
      all.sort((a,b)=>progress(b)-progress(a));
      const k=Math.min(all.length-1,Math.floor(all.length*0.1));
      pos=all[k];
    }
    const dx=FX-pos[0],dy=FY-pos[1],dist=Math.hypot(dx,dy);
    const pr=progress(pos);
    if(pr>bestProg+3){bestProg=pr;stallSteps=0;} else stallSteps++;
    let pushers=N,tol=6;
    if(dist<1500)pushers=2;
    if(dist<70){pushers=1;tol=1.5;}
    let keys=dirKeys(dx,dy,tol);
    // stall recovery: if no progress for a while, wiggle perpendicular to unstick
    if(stallSteps>=4){ wiggle=(wiggle+1)%4; const w=[['KeyW'],['KeyS'],['KeyD'],['KeyA']][wiggle]; keys=new Set(w); if(step%2===0) keys=dirKeys(dx,dy,tol); }
    for(let i=0;i<pages.length;i++){ if(i<pushers) await press(pages[i],keys); else await press(pages[i],new Set()); }
    if(step%8===0){ for(const i of dead){ log("client",i,"disconnected; rejoining"); try{const ws=await join(pages[i]); log("client",i,"rejoined ws",ws);}catch(e){} } }
    const st={t:Math.round((now-t0)/1000),pos:[Math.round(pos[0]),Math.round(pos[1])],dist:Math.round(dist),prog:Math.round(pr),bestProg:Math.round(bestProg),stall:stallSteps,reads:all.length,pushers,keys:[...keys],flag};
    fs.writeFileSync('status.json',JSON.stringify(st));
    if(step%5===0)log(JSON.stringify(st));
    if(flag){fs.writeFileSync('FLAG.txt',flag);log("CAPTURED",flag);break;}
    if(now-t0>150*60*1000){log("timeout");break;}
    await sleep(dist<70?300:1000);
  }
  await sleep(1500);await browser.close();
})().catch(e=>{console.error("FATAL",e);fs.writeFileSync('status.json',JSON.stringify({error:String(e)}));process.exit(1)});
