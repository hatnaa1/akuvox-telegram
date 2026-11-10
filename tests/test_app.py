import os
import smtplib
import threading
import unittest
from email.message import EmailMessage
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import requests
from aiosmtpd.controller import Controller

from app import Bridge, DeliveryError, MailHandler, http_handler


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'TELEGRAM_TOKEN': 'local-test', 'TELEGRAM_CHAT_ID': 'local-test',
            'SMTP_USER': 'local-user', 'SMTP_PASS': 'local-password',
            'WEBHOOK_TOKEN': 'local-webhook', 'COOLDOWN_S': '15',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bridge = Bridge()
        self.calls = []
        self.bridge.api = lambda *args: self.calls.append(args)

    def message(self, count=0):
        msg = EmailMessage()
        msg['From'] = 'r20@akuvox.local'
        msg['To'] = 'alerts@akuvox.local'
        msg['Subject'] = 'Akuvox test'
        msg.set_content('Тест')
        for i in range(count):
            msg.add_attachment(b'\xff\xd8\xffphoto', maintype='application',
                               subtype='octet-stream', filename=f'{i}.jpg')
        return msg

    def test_mime_and_album(self):
        self.bridge.mail(self.message().as_bytes())
        self.assertIn('✅ Домофон Email тест амжилттай', self.calls[-1][1]['text'])
        self.bridge.mail(self.message(1).as_bytes())
        self.assertEqual(self.calls[-1][0], 'sendPhoto')
        self.bridge.mail(self.message(11).as_bytes())
        self.assertEqual([c[0] for c in self.calls[-2:]], ['sendMediaGroup', 'sendPhoto'])

    def test_cooldown_and_failure(self):
        self.assertTrue(self.bridge.deliver('motion', 'motion'))
        self.assertFalse(self.bridge.deliver('motion', 'motion'))
        self.assertTrue(self.bridge.deliver('door', 'door'))
        self.assertTrue(self.bridge.deliver('motion', 'test', test=True))
        def fail(*args):
            raise DeliveryError('test failure')
        self.bridge.api = fail
        with self.assertRaises(DeliveryError):
            self.bridge.deliver('new', 'new')
        self.assertNotIn('new', self.bridge.last)

    def test_smtp_auth(self):
        # Controller needs a concrete port for its startup probe.
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        controller = Controller(MailHandler(self.bridge), hostname='127.0.0.1', port=port,
                                auth_required=True, auth_require_tls=False,
                                authenticator=self.bridge.authenticate)
        controller.start()
        self.addCleanup(controller.stop)
        with smtplib.SMTP('127.0.0.1', port, timeout=5) as smtp:
            with self.assertRaises(smtplib.SMTPSenderRefused):
                smtp.send_message(self.message())
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                smtp.login('wrong', 'wrong')
            smtp.login('local-user', 'local-password')
            smtp.send_message(self.message(1))
        # Explicit LOGIN, as smtplib.login prefers PLAIN.
        with smtplib.SMTP('127.0.0.1', port, timeout=5) as smtp:
            smtp.ehlo()
            smtp.user, smtp.password = 'local-user', 'local-password'
            smtp.auth('LOGIN', smtp.auth_login)
            smtp.send_message(self.message())
        self.assertEqual(len(self.calls), 2)

    def test_anonymous_smtp(self):
        import socket
        self.bridge.user = ''
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        controller = Controller(MailHandler(self.bridge), hostname='127.0.0.1', port=port,
                                auth_required=False, auth_require_tls=False,
                                authenticator=self.bridge.authenticate)
        controller.start()
        self.addCleanup(controller.stop)
        with smtplib.SMTP('127.0.0.1', port, timeout=5) as smtp:
            smtp.send_message(self.message())
        self.assertEqual(self.calls[-1][0], 'sendMessage')

    def test_http(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), http_handler(self.bridge))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        self.assertEqual(requests.get(base + '/health', timeout=5).json(), {'status': 'ok'})
        self.assertEqual(requests.get(base + '/event', timeout=5).status_code, 403)
        url = base + '/event?token=local-webhook&type=motion'
        self.assertEqual(requests.get(url, timeout=5).json()['status'], 'sent')
        self.assertEqual(requests.get(url, timeout=5).json()['status'], 'cooldown')
        response = requests.post(url + '&test=1', data=b'\x89PNG\r\n\x1a\nphoto', timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls[-1][0], 'sendPhoto')
        self.assertEqual(requests.post(url, data=b'invalid',
                                      headers={'Content-Type': 'application/octet-stream'},
                                      timeout=5).status_code, 415)


if __name__ == '__main__':
    unittest.main()
