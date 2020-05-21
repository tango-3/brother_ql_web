#!/usr/bin/env python

import logging
import threading

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)


# Use a service account
cred = credentials.Certificate('/home/pi/cv-test-system-prod-firebase-adminsdk-rbmrc-012ad6b866.json')

class Firestore:
  
  def __init__(self):
    logger.debug('Init Firestore')
    firebase_admin.initialize_app(cred)
   
  def connect(self, serial, branch, version):
    self.db = firestore.client()
    self.printerRef = self.db.collection('printers').document(serial)
    self.printerRef.set({
        u'branch': branch,
        u'version': version,
        u'lastConnectedTimestamp': firestore.SERVER_TIMESTAMP
    }, merge=True)
  
  def listen(self, callback):
    # Create an Event for notifying main thread.
    callback_done = threading.Event()
    # Create a callback on_snapshot function to capture changes
    def on_snapshot(doc_snapshot, changes, read_time):
      for change in changes:
        if change.type.name == 'ADDED':
            print(u'New Label: {}'.format(change.document.id))
            print(u'Document data: {}'.format(change.document.to_dict()))
            callback(change.document.to_dict())
            change.document.reference.delete()

      if len(changes) == 0:
        for doc in doc_snapshot:
          print(u'Received document snapshot: {}'.format(doc.id))
          print(u'Document data: {}'.format(doc.to_dict()))
          callback(doc.to_dict())
          doc.reference.delete()
      callback_done.set()

    doc_ref = self.printerRef.collection('labels')

    # Watch the document
    self.doc_watch = doc_ref.on_snapshot(on_snapshot)
    # [END listen_document]
  def ping(self):
    self.printerRef.set({
        u'lastPing': firestore.SERVER_TIMESTAMP
    }, merge=True)

  def close(self):
    if not self.doc_watch is None:
      self.doc_watch.unsubscribe()
