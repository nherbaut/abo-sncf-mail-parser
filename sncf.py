#!/usr/bin/python3

import aiosmtpd.controller

import os.path


import logging
import aiosmtpd.handlers
from ics import Calendar, Event
import email
import quopri
import dateparser
from lxml.html.soupparser import fromstring
import pickle
import argparse
import ssl


class SNCFHandler(aiosmtpd.handlers.Message):

    def __init__(self,output_dir):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.output_dir=output_dir

    async def handle_DATA(self, server, session, envelope):
        # If the server was created with decode_data True, then data will be a
        # str, otherwise it will be bytes.
        data = envelope.content
        if isinstance(data, bytes):
            message = email.message_from_bytes(data, self.message_class)
        else:
            assert isinstance(data, str), ('Expected str or bytes, got {}'.format(type(data)))
            message = email.message_from_string(data, self.message_class)

        self.logger.debug("got message from SMTP: from={}, to={}".format(message["from"], message["to"]))
        self.handle_sncf_message(message)

        return '250 OK'

    def handle_sncf_message(self, message):
        payload = list(message.walk())[1].get_payload()
        payload = payload.replace("\r", "").replace("\n", "").replace("=20", "")
        root = fromstring(
            quopri.decodestring(payload).decode("latin1").replace("\t", "").replace("\n", "").replace('\\xa0', ' '))
        departure_city, _, arrival_city, _, seat_info, duration, _ = [r.replace("\xa0", " ") for r in root.xpath(
            "//table/tr/td/table/tr/td/table/tr/td/span/text()")]
        departure_time, train_id, ticket_id, arrival_time = [r.replace("\xa0", " ") for r in root.xpath(
            "//table/tr/td/table/tr/td/table/tr/td/span/b/text()")]
        departure_date = [r.replace("\xa0", " ") for r in root.xpath("//html/body/table/tr/td/table/tr/td/span/text()")]

        c=None
        target_file=os.path.join(self.output_dir,"calendar.ics")

        if os.path.isfile(target_file):
            with open(target_file, "r") as f:
                c = Calendar(f.read())
        if c is None:
            c = Calendar()

        e = Event()
        e.name = "%s: %s -> %s [%s]" % (train_id, departure_city, arrival_city, ticket_id)
        e.begin = dateparser.parse("%s %s CEST" % (departure_date, departure_time), languages=["fr"])
        e.end = dateparser.parse("%s %s CEST    " % (departure_date, arrival_time), languages=["fr"])
        e.location = departure_city
        e.description = "%s" % seat_info

        #weird. sometimes it's list, sometime it's set...
        if type(c.events) is list:
            c.events.append(e)
        else:
            c.events.add(e)

        with open(target_file, 'w') as f:
            f.writelines(c)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('hostname',metavar='HOSTNAME');
    parser.add_argument('port',metavar='SMTP_PORT');
    parser.add_argument('output_dir',metavar='DIR');
    parser.add_argument('http_port',metavar='HTTP_PORT',type=int);
    parser.add_argument('cert_dir',nargs='?', metavar='CERT_DIR',default=None);
    args = parser.parse_args()




    controller = aiosmtpd.controller.Controller(SNCFHandler(args.output_dir),  port=args.port,hostname=args.hostname)

    if(args.cert_dir is not None):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(os.path.join(args.cert_dir,'cert.pem'), os.path.join(args.cert_dir,'key.pem'))
        controller.ssl_context=context
    controller.start()

    import http.server
    import socketserver



    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, request, client_address, server):
            http.server.SimpleHTTPRequestHandler.__init__(self, request, client_address, server)

    Handler = CustomHandler

    os.chdir(args.output_dir)
    with socketserver.TCPServer(("", args.http_port), Handler) as httpd:
        httpd.serve_forever()


    controller.stop()
