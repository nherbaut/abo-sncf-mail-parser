import email
import logging
import queue
import aiosmtpd.controller
import aiosmtpd.handlers
from ics import Calendar, Event
import email
import quopri
import dateparser
from lxml.html.soupparser import fromstring


class SNCFHandler( aiosmtpd.handlers.Message ):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    async def handle_DATA(self, server, session, envelope):
        # If the server was created with decode_data True, then data will be a
        # str, otherwise it will be bytes.
        data = envelope.content
        if isinstance(data, bytes):
            message = email.message_from_bytes(data, self.message_class)
        else:
            assert isinstance(data, str), ( 'Expected str or bytes, got {}'.format(type(data)))
            message = email.message_from_string(data, self.message_class)

        self.logger.debug( "got message from SMTP: from={}, to={}".format(message["from"], message["to"]) )
        self.handle_sncf_message(message)

        return '250 OK'

    def handle_sncf_message(self,message):
        payload=list(message.walk())[1].get_payload()

        root=fromstring(quopri.decodestring(payload).decode("latin1").replace("\t","").replace("\n","").replace('\\xa0', ' '))
        departure_city,_,arrival_city,_,seat_info,duration,_=[r.replace("\xa0"," ") for r in root.xpath("//table/tr/td/table/tr/td/table/tr/td/span/text()")]
        departure_time,train_id,ticket_id,arrival_time=[r.replace("\xa0"," ") for r in root.xpath("//table/tr/td/table/tr/td/table/tr/td/span/b/text()")]
        departure_date=[r.replace("\xa0"," ") for r in root.xpath("//html/body/table/tr/td/table/tr/td/span/text()")]

        c = Calendar()
        e = Event()
        e.name = "%s: %s -> %s [%s]" % (train_id,departure_city,arrival_city,ticket_id)
        e.begin = dateparser.parse("%s %s CEST"%(departure_date,departure_time),languages=["fr"])
        e.end = dateparser.parse("%s %s CEST    "%(departure_date,arrival_time),languages=["fr"])
        e.location=departure_city
        e.description="%s" %seat_info
        c.events.add(e)
        c.events

        with open('my.ics', 'w') as f:
          f.writelines(c)
