from http.server import BaseHTTPRequestHandler, HTTPServer

from jinja2 import Environment, FileSystemLoader

environment = Environment(loader=FileSystemLoader("./"))



data = {
    "title": "Test"
}

class Jinja2HTTP(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)

    def do_GET(self):
        template = environment.get_template("add_inverter.jinja2")
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        html = template.render(data)
        self.wfile.write(bytes(html, 'utf-8'))


if __name__ == "__main__":        
    webServer = HTTPServer(("localhost", 3030), Jinja2HTTP)
    print("Server started http://%s:%s" % ("localhost", 3030))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")