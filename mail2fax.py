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

    print(call)

    callfile.write(call)
    callfile.close()
    
    return callfile_name


if __name__ == "__main__":
    try:
        root_mailbox = mailbox.Maildir(MAILDIR, factory=None)
        for key in root_mailbox.iterkeys():
            print("\n-------------\n")
            message = mailbox.MaildirMessage(root_mailbox[key])
            if 'S' in message.get_flags():
                continue
            message.set_flags('S')
            message.set_subdir("cur")
            root_mailbox[key] = message

            to = message['to']
            from_address = re.search("<?([a-zA-Z0-9_.]+@[a-zA-Z0-9_.]+\.\w{2,5})>?", message['from'], flags=0)

            if not from_address:
                continue
            print("\tTo:", to)
            print("\tFrom:", from_address.group(1))
            callerid = callerid_from_email(from_address.group(1))
            print("CallerID:", callerid)

            if callerid < 0:
                print("\nUser ", from_address.group(1), " not found\n")
                continue
            number = re.search("^(\d+)@[a-zA-Z0-9_.]+\.\w{2,5}", to, flags=0)

            if not number:
                continue

            print("\tDir: ", message.get_subdir())
            print("\tNumber: ", number.group(1))
            root_mailbox[key] = message
            root_mailbox.flush()
            print("\tFlags: ", root_mailbox[key].get_flags())

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
                os.rename(TMP_DIR + "/" + callfile, "/var/spool/asterisk/outgoing" + "/" + callfile)
    finally:
        root_mailbox.close()

