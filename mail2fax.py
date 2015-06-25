#!/usr/bin/env python2
from __future__ import print_function
import mailbox
import re
import mysql.connector
import time
import os
import subprocess

#import PythonMagick

MAILDIR = "/root/Maildir"
TMP_DIR="/tmp"


def callerid_from_email(email_address):
    try:
        cnx = mysql.connector.connect(user='root', database='fax')

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Wrong username or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    cursor = cnx.cursor()
    cursor.execute(
        'SELECT number FROM fax_users WHERE email="%s"' %
        email_address)
    try:
        callerid = cursor.fetchone()[0]
    except TypeError:
        callerid = -1

    cursor.close()
    cnx.close()
    return callerid

def create_callfile(destination,callerid,email,filename):
    callfile_name = str(callerid) + str(destination) + str(time.time()) + ".call"
    callfile_path = TMP_DIR + "/" + callfile_name
    try:
        callfile = open(callfile_path, "w")
    except IOError as err:
        print("Failed to open", callfile_path)
        print(err)
        exit(1)
            
    call = "Channel: Local/" + destination + "@outbound-allroutes\n"
    call += "CallerID: FAX <" + str(callerid) + ">\n"
    call += "WaitTime: 60\n"
    call += "Archive: yes\n"
    call += "Context: outboundfax\n"
    call += "Extension: s\n"
    call += "Priority: 1\n"

    # FAX Options
    call += "Set: FAXFILE=" + filename + "\n"
    call += "Set: FAXHEADER=" + str(callerid) + "\n"
    call += "Set: LOCALID=" + str(callerid) + "\n"
    call += "Set: EMAIL=" + email + "\n"
    call += "Set: DESTINATION=" + destination + "\n"

    callfile.write(call)
    callfile.close()
    
    return callfile_name


if __name__ == "__main__":
    try:
        selected_mailbox = mailbox.Maildir(MAILDIR, factory=None)
        for key in selected_mailbox.iterkeys():
            message = mailbox.MaildirMessage(selected_mailbox[key])
            if 'S' in message.get_flags():
                continue
            message.set_flags('S')
            message.set_subdir("cur")
            selected_mailbox[key] = message

            to = message['to']
            from_address = re.match("([a-zA-Z0-9_.]+@[a-zA-Z0-9_.]+\.\w{2,5})", message['from'], flags=0)

            if not from_address:
                continue

            callerid = callerid_from_email(from_address.group(1))

            if callerid < 0:
                print("\nUser ", from_address.group(1), " not found\n")
                continue
            number = re.match("^(\d+)@[a-zA-Z0-9_.]+\.\w{2,5}", to, flags=0)

            if not number:
                continue

            selected_mailbox[key] = message
            selected_mailbox.flush()

            if not message.is_multipart():
                continue
            pdf_file = None
            for part in message.walk():
                if part.get_content_type()!="application/pdf":
                    continue
                pdf_file_name = part.get_filename()
                print("\tPart filename: ", pdf_file_name)

                pdf_file = part.get_payload(decode=True)

                if pdf_file:
                    # Save the PDF file
                    pdf_file_path = TMP_DIR + "/" + pdf_file_name
                    tiff_file_path = pdf_file_path + ".tiff"
                    f = open(pdf_file_path, 'w')
                    f.write(pdf_file)
                    f.close()

                    res = subprocess.call(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=tiffg4", "-sOutputFile=" + tiff_file_path, "-f", pdf_file_path])
                    if res == 0:
                        os.remove(pdf_file_path)
                    else:
                        print("Tiff conversion failed")

                    callfile = create_callfile(number.group(1), callerid, from_address.group(1), tiff_file_path)
                    # We only want one PDF file
                    break
            if callfile:
                print("FAX File created:", from_address.group(1), callerid, number.group(1))
                os.rename(TMP_DIR + "/" + callfile, "/var/spool/asterisk/outgoing" + "/" + callfile)
    finally:
        selected_mailbox.close()

