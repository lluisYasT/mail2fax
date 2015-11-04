#!/usr/bin/env python2
# set ts=4 sts=4 sw=4 expandtab
from __future__ import print_function
import mailbox
import re
import mysql.connector
import time
import os
import subprocess
import logging

#import PythonMagick

MAILDIR = "/home/asterisk/Maildir"
TMP_DIR="/tmp"


def callerid_from_email(email_address):
    try:
        cnx = mysql.connector.connect(user='root', database='fax')

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logging.warning("Wrong username or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logging.warning("Database does not exist")
        else:
            logging.warning(err)
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

def create_callfile(destination,callerid,email,filenames):
    filename = ""
    if len(filenames) == 1:
        filename = filenames[0]
        fax_file_line = "Set: FAXOPT(filename)=" + filename + "\n"
        fax_file_line += "Set: FAXFILE=" + filename + "\n"
        logging.debug("Fax_file_line: " + fax_file_line)
    elif len(filenames) > 1:
        filename = ",".join(filenames)
        filename_sendfax = "&".join(filenames)
        fax_file_line = "Set: FAXOPT(filenames)=" + filename + "\n"
        fax_file_line += "Set: FAXFILE=" + filename_sendfax + "\n"
        logging.debug("Fax_file_line: " + fax_file_line)

    if not filename:
        return -1

    print(filename)
    callfile_name = str(callerid) + str(destination) + str(time.time()) + ".call"
    callfile_path = os.path.join(TMP_DIR, callfile_name)

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
    call += fax_file_line
    call += "Set: FAXHEADER=" + str(callerid) + "\n"
    call += "Set: LOCALID=" + str(callerid) + "\n"
    call += "Set: EMAIL=" + email + "\n"
    call += "Set: DESTINATION=" + destination + "\n"

    logging.debug("Callfile contents: " + call)
    callfile.write(call)
    callfile.close()
    
    return callfile_name


if __name__ == "__main__":
    logging.basicConfig(filename='/var/log/asterisk/mail2fax.log',format='[%(asctime)s]\t%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
    try:
        selected_mailbox = mailbox.Maildir(MAILDIR, factory=None)
        for key in selected_mailbox.iterkeys():
            tiff_file_paths = []
            message = mailbox.MaildirMessage(selected_mailbox[key])
            if 'S' in message.get_flags():
                continue
            message.set_flags('S')
            message.set_subdir("cur")
            selected_mailbox[key] = message

            to = message['X-Original-To']
            from_address = re.search("<?([a-zA-Z0-9_.]+@[a-zA-Z0-9_.-]+\.\w+)>?", message['from'], flags=0)

            if not from_address:
                logging.warning("Incorrect FROM header: " + message['from'])
                continue
            logging.debug("From: " + from_address.group(1))

            callerid = callerid_from_email(from_address.group(1))

            if callerid < 0:
                logging.info("User " + from_address.group(1) + " not found")
                continue

            number = re.search("<?(\d+)@[a-zA-Z0-9_.]+\.\w{2,5}>?", to, flags=0)

            if not number:
                logging.warning("Wrong number in: " + to)
                continue

            logging.debug("Number: " + number.group(1))

            selected_mailbox[key] = message
            selected_mailbox.flush()

            if not message.is_multipart():
                logging.warning("No files attached")
                continue
            pdf_file = None
            for part in message.walk():
                logging.debug(part.get_content_type())
                if part.get_content_type()=="application/pdf" or part.get_content_type()=="image/tiff":
                    file_name = part.get_filename()
                    logging.info("Part filename: " + file_name)
                    file_content = part.get_payload(decode=True)

                    file_path = os.path.join(TMP_DIR, file_name)
                    file_fd = open(file_path, 'w')
                    file_fd.write(file_content)
                    file_fd.close()
                    tiff_file_path = file_path
                    if part.get_content_type()=="application/pdf":
                        tiff_file_path = file_path + ".tiff"
                        res = subprocess.call(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=tiffg4", "-sOutputFile=" + tiff_file_path, "-f", file_path])
                        if res == 0:
                            os.remove(file_path)
                        else:
                            logging.warning("Tiff conversion failed")
                            tiff_file_path = None

                    tiff_file_paths.append(tiff_file_path)

            callfile = create_callfile(number.group(1), callerid, from_address.group(1), tiff_file_paths)
            if callfile == -1:
                logging.warning("Error creating callfile")
                break

            if callfile:
                logging.info("FAX File created:" + from_address.group(1) + str(callerid) + number.group(1))
                os.rename(os.path.join(TMP_DIR, callfile), os.path.join("/var/spool/asterisk/outgoing", callfile))
    finally:
        selected_mailbox.close()

