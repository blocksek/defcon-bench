(function(){
  window.__frames=[]; window.__flag=null; window.__wsList=[]; window.__lastIn=[];
  function tryExtract(u,i,stride){
    // stride=1 for UTF-8, 2 for UTF-16LE. Expect 'b','b','b','{' then chars until '}'
    if(u[i]!==98||u[i+stride]!==98||u[i+2*stride]!==98||u[i+3*stride]!==123) return null;
    var s=''; var j=i;
    for(var n=0;n<300;n++){ var c=u[j]; if(c===undefined) break; if(c>=32&&c<127) s+=String.fromCharCode(c); if(c===125) return s; j+=stride; }
    return null;
  }
  function scan(buf){
    try{ var u=new Uint8Array(buf);
      for(var i=0;i+8<u.length;i++){
        var a=tryExtract(u,i,1); if(a&&a.indexOf('bbb{')===0){window.__flag=a;console.log('FLAGFOUND '+a);return;}
        var b=tryExtract(u,i,2); if(b&&b.indexOf('bbb{')===0){window.__flag=b;console.log('FLAGFOUND '+b);return;}
      }
    }catch(e){}
  }
  var O=window.WebSocket;
  window.WebSocket=function(url,protos){console.log("WS_NEW "+url);var ws=protos!==undefined?new O(url,protos):new O(url);window.__wsList.push(ws);ws.binaryType='arraybuffer';
    ws.addEventListener('message',function(ev){var len=0,buf=null;if(ev.data instanceof ArrayBuffer){len=ev.data.byteLength;buf=ev.data;}window.__frames.push({t:Date.now(),len,dir:'in'});if(buf){window.__lastIn.push(new Uint8Array(buf.slice(0)));if(window.__lastIn.length>400)window.__lastIn.shift();scan(buf);}});
    var s=ws.send.bind(ws);ws.send=function(d){var len=d&&d.byteLength!==undefined?d.byteLength:(d&&d.length)||0;window.__frames.push({t:Date.now(),len,dir:'out'});return s(d);};
    return ws;};
  window.WebSocket.prototype=O.prototype;window.WebSocket.OPEN=1;window.WebSocket.CLOSED=3;window.WebSocket.CONNECTING=0;window.WebSocket.CLOSING=2;
})();
