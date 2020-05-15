## Modified from brother\_ql\_web

This is a web service to print labels on Brother QL label printers.

You need Python 3 for this software to work.

To start the server, run `./brother_ql_web.py`. 


### Usage

Once it's running, the service will connect to firestore using a cert in the users profile and print labels as they are request in the firestore label collection.  Also sends a ping every 4 secs to let clients know that the printer is still there.

### License

This software is published under the terms of the GPLv3, see the LICENSE file in the repository.

Parts of this package are redistributed software products from 3rd parties. They are subject to different licenses:

* [Bootstrap](https://github.com/twbs/bootstrap), MIT License
* [Glyphicons](https://getbootstrap.com/docs/3.3/components/#glyphicons), MIT License (as part of Bootstrap 3.3)
* [jQuery](https://github.com/jquery/jquery), MIT License
