"""Forwards to the local service and adds the QA seller's token, standing in for Stack's cookie."""
import http.server, urllib.request, urllib.error, socketserver
UP="http://127.0.0.1:8801"
class H(http.server.BaseHTTPRequestHandler):
    def _go(self):
        n=int(self.headers.get("Content-Length") or 0); body=self.rfile.read(n) if n else None
        h={k:v for k,v in self.headers.items() if k.lower() not in("host","content-length","authorization","connection")}
        h["Authorization"]="Bearer "+open("tok_a").read().strip()
        r=urllib.request.Request(UP+self.path, data=body, method=self.command, headers=h)
        try: f=urllib.request.urlopen(r); code=f.status
        except urllib.error.HTTPError as e: f=e; code=e.code
        data=f.read(); self.send_response(code)
        for k,v in f.headers.items():
            if k.lower() not in("transfer-encoding","connection","content-length","server","date"): self.send_header(k,v)
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=do_OPTIONS=_go
    def log_message(self,*a): open("proxy.log","a").write(self.command+" "+self.path+"\n")
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads=True
S(("127.0.0.1",8802),H).serve_forever()
