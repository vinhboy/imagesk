import cgi
import os
import urllib
import string
import re
import logging

from random import Random
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import blobstore_handlers

class Greeting(db.Model):
    author = db.UserProperty()
    content = db.StringProperty(multiline=True)
    date = db.DateTimeProperty(auto_now_add=True)

class Image(db.Model):
    filename = db.StringProperty(multiline=False)
    blob_key = blobstore.BlobReferenceProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    source = db.TextProperty()
    ip = db.StringProperty(multiline=True)
    
class MainPage(webapp.RequestHandler):
    def get(self):
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        
        upload_url = blobstore.create_upload_url('/upload')
        
        if self.request.get('i'):
          image = Image.gql("WHERE filename = :1",self.request.get('i')).get()
          if image:
            # captures IP address on initial load
            if image.ip == None:
              image.ip = self.request.remote_addr
              image.put()
          else:
            self.redirect('/?error=not_found')
        
        template_values = {
            'upload_url': upload_url,
            'user': users.get_current_user(),
            'url': url,
            'url_linktext': url_linktext,
            'error': self.request.get('error'),
            'image': self.request.get('i')
        }

        if self.request.get('upload_url'):
          self.response.out.write(upload_url)
        else:
          if (self.request.get('image_url')):
            self.response.out.write('http://imagesk.com/'+self.request.get('i'))
          else:
            path = os.path.join(os.path.dirname(__file__), 'index.html')
            self.response.out.write(template.render(path, template_values))

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        if self.get_uploads('file'):
          upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
          blob_info = upload_files[0]
          
          image = Image()
          image.source = str(self.request.headers)
          image.blob_key = blob_info
        
          file_name = ''.join(Random().sample(string.letters+string.digits,8))
          file_extension = re.search('^image/(jpeg|jpg|gif|png|tiff|bmp)$',blob_info.content_type)
        
          url = ''
        
          if blob_info.size > 2097152:
            url = '?error=too_big'
          
          if file_extension:
            file_extension = file_extension.group(1)
            file_extension = file_extension.replace('jpeg','jpg')
            image.filename = file_name+'.'+file_extension
          else:
            url = '?error=file_type'
        
          duplicate = Image.gql("WHERE filename = :1",image.filename).get()
          if duplicate:
            url = '?error=duplicate'
        
          if url:
            blobstore.delete(blob_info.key())
          else:
            image.put()
            url = '?i=' + image.filename
            if (self.request.get('image_url')):
              url += '&image_url=true'
            
        else:
          url = '?error=crap'
        
        self.redirect('/' + url)

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, resource):
        filename = str(urllib.unquote(resource))
        image = Image.gql("WHERE filename = :1",filename).get()
        
        #self.response.out.write(images[0].blob_key.size)
        if image:
          self.send_blob(image.blob_key)
        else:
          self.error(404)

class Guestbook(webapp.RequestHandler):
    def post(self):
        greeting = Greeting()

        if users.get_current_user():
            greeting.author = users.get_current_user()

        greeting.content = self.request.get('content')
        greeting.put()
        self.redirect('/')

application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/upload', UploadHandler),
                                      ('/([a-zA-Z0-9_-]+\.(?:jpg|jpeg|bmp|tiff|gif|png)$)?', ServeHandler),
                                      ('/sign', Guestbook)],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()