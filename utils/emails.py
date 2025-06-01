from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail, Email, To, Content
import os
from flask import render_template

def trimite_email_resetare(destinatar, link_reset):
    continut = render_template('email/reset_parola.html', reset_link=link_reset)
    mesaj = SGMail(
        from_email=Email('timicampark@gmail.com'),
        to_emails=To(destinatar),
        subject='Resetare parolă - TimiCamPark',
        html_content=Content("text/html", continut)
    )
    return trimite_mesaj_sendgrid(mesaj)

def trimite_email_confirmare_abonament(destinatar, abonament):
    continut = render_template('email/confirmare_abonament.html', abonament=abonament)
    mesaj = SGMail(
        from_email=Email('timicampark@gmail.com'),
        to_emails=To(destinatar),
        subject='Confirmare Abonament - TimiCamPark',
        html_content=Content("text/html", continut)
    )
    return trimite_mesaj_sendgrid(mesaj)

def trimite_email_reminder_expirare(destinatar, numar_inmatriculare, data_sfarsit):
    continut = render_template('email/notificare_expirare.html',
                               numar_inmatriculare=numar_inmatriculare,
                               data_sfarsit=data_sfarsit)
    mesaj = SGMail(
        from_email=Email('timicampark@gmail.com'),
        to_emails=To(destinatar),
        subject='Reminder: Abonament aproape de expirare - TimiCamPark',
        html_content=Content("text/html", continut)
    )
    return trimite_mesaj_sendgrid(mesaj)

def trimite_mesaj_sendgrid(mesaj):
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(mesaj)
        print(f"Email trimis (status: {response.status_code})")
        return True
    except Exception as e:
        print(f"Eroare trimitere email: {e}")
        return False
