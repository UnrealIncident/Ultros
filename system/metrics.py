import urllib

__author__ = 'Gareth Coles'

import json
import urllib2
import traceback

from twisted.internet.task import LoopingCall

from system.decorators import run_async_threadpool
from system.event_manager import EventManager
from system.singleton import Singleton
from system.storage.formats import JSON
from system.storage.manager import StorageManager

from utils.log import getLogger
from utils.packages.packages import Packages

from system.translations import Translations
_ = Translations().get()


warning = """
                                 .i;;;;i.
                               iYcviii;vXY:
                             .YXi       .i1c.
                            .YC.     .    in7.
                           .vc.   ......   ;1c.
                           i7,   ..        .;1;
                          i7,   .. ...      .Y1i
                         ,7v     .6MMM@;     .YX,
                        .7;.   ..IMMMMMM1     :t7.
                       .;Y.     ;$MMMMMM9.     :tc.
                       vY.   .. .nMMM@MMU.      ;1v.
                      i7i   ...  .#MM@M@C. .....:71i
                     it:   ....   $MMM@9;.,i;;;i,;tti
                    :t7.  .....   0MMMWv.,iii:::,,;St.
                   .nC.   .....   IMMMQ..,::::::,.,czX.
                  .ct:   ....... .ZMMMI..,:::::::,,:76Y.
                  c2:   ......,i..Y$M@t..:::::::,,..inZY
                 vov   ......:ii..c$MBc..,,,,,,,,,,..iI9i
                i9Y   ......iii:..7@MA,..,,,,,,,,,....;AA:
               iIS.  ......:ii::..;@MI....,............;Ez.
              .I9.  ......:i::::...8M1..................C0z.
             .z9;  ......:i::::,.. .i:...................zWX.
             vbv  ......,i::::,,.      ................. :AQY
            c6Y.  .,...,::::,,..:t0@@QY. ................ :8bi
           :6S. ..,,...,:::,,,..EMMMMMMI. ............... .;bZ,
          :6o,  .,,,,..:::,,,..i#MMMMMM#v.................  YW2.
         .n8i ..,,,,,,,::,,,,.. tMMMMM@C:.................. .1Wn
         7Uc. .:::,,,,,::,,,,..   i1t;,..................... .UEi
         7C...::::::::::::,,,,..        ....................  vSi.
         ;1;...,,::::::,.........       ..................    Yz:
          v97,.........                                     .voC.
           izAotX7777777777777777777777777777777777777777Y7n92:
             .;CoIIIIIUAA666666699999ZZZZZZZZZZZZZZZZZZZZ6ov.
"""


class Metrics(object):
    """
    Configurable metrics handler.

    This sends some basic stats to the site over at http://ultros.io/metrics
    when configured.
    """

    __metaclass__ = Singleton

    storage = None
    events = None
    packages = None

    config = {}
    log = None
    task = None
    manager = None

    interval = 300  # Every 5 minutes

    domain = "https://ultros.io"

    submit_url = domain + "/api/metrics/post/%s"
    exception_url = domain + "/api/metrics/post/exception/%s"
    uuid_url = domain + "/api/metrics/get/uuid"
    destroy_url = domain + "/api/metrics/destroy/%s"

    uuid = ""

    def __init__(self, config=None, manager=None):
        if config is None or manager is None:
            raise ValueError("Config and manager must not be None!")

        self.config = config
        self.manager = manager
        self.log = getLogger("Metrics")

        self.storage = StorageManager()
        self.events = EventManager()
        self.packages = Packages(get=False)

        self.data = self.storage.get_file(self, "data", JSON, "metrics.json")

        self.task = LoopingCall(self.submit_metrics)

        if "metrics" in config:
            self.status = config["metrics"]
            if self.status == "on":
                self.status = True
            elif self.status == "off":
                self.status = False
        else:
            self.log.warn("\n%s\n" % warning)
            self.log.warn(_(
                "We couldn't find a \"metrics\" option in your settings.yml"
                " file!"
            ))
            self.log.warn(_(
                "Metrics will default to being turned on. If this is not what"
                " you want, please create \"metrics\" option in your settings"
                " and set it to \"off\"."
            ))
            self.log.warn(_(
                "If you want to keep metrics enabled, set the option to"
                " \"on\"."
            ))
            self.log.warn(_(
                "This warning will be shown on every startup until the option"
                " has been set."
            ))
            self.status = True

        with self.data:
            if self.status is True:
                if "uuid" not in self.data:
                    try:
                        uuid = self.get(self.uuid_url)
                    except Exception:
                        self.log.exception(_("Error getting UUID"))
                        return
                    self.data["uuid"] = uuid
                    self.data["status"] = "enabled"
            elif "uuid" not in self.data:
                self.data["status"] = "disabled"

        if self.status is False:
            if self.data["status"] == "disabled":
                self.log.info(_("Metrics are disabled."))
                return
        elif self.status is "destroy":
            if "uuid" not in self.data:
                self.log.info(_("Metrics are disabled."))
                return

        self.task.start(self.interval)

    @run_async_threadpool
    def submit_metrics(self):
        self.log.debug(_("Firing task."))
        compiled = {"plugins": [], "packages": [], "protocols": []}
        if self.status is True:
            self.log.debug(_("Submitting metrics."))
            compiled["plugins"] = self.manager.loaded_plugins.keys()
            compiled["packages"] = self.packages.get_installed_packages()

            for name in self.manager.factories.keys():
                proto = self.manager.get_protocol(name)
                compiled["protocols"].append(proto.TYPE)

            try:
                compiled["enabled"] = True
                r = self.post(self.submit_url % self.data["uuid"], compiled)
                r = json.loads(r)

                self.log.debug(_("Submitted. Result: %s") % r)

                if r["result"] == "error":
                    self.log.error(_("Error submitting metrics: %s")
                                   % r["error"])
            except Exception:
                self.log.exception(_("Error submitting metrics"))
        elif self.status is False:
            self.log.debug(_("Submitting disable message."))
            try:
                compiled["enabled"] = False
                r = self.post(self.submit_url % self.data["uuid"], compiled)
                r = json.loads(r)

                self.log.debug(_("Submitted. Result: %s") % r)

                if r["result"] == "error":
                    self.log.error(_("Error submitting disable message: %s")
                                   % r["error"])
            except Exception:
                self.log.exception(_("Error submitting disable message"))
            else:
                with self.data:
                    self.data["status"] = "disabled"
            finally:
                self.task.stop()
        elif self.status == "destroy":
            self.log.debug(_("Submitting destruction message."))
            try:
                r = self.get(self.destroy_url % self.data["uuid"])
                r = json.loads(r)

                self.log.debug("Submitted. Result: %s" % r)

                if r["result"] == "success":
                    self.log.info(_("Metrics data has been removed from the "
                                    "server."))
                else:
                    self.log.warn(_("Unknown UUID, data was already removed "
                                    "from the server."))
            except Exception:
                self.log.exception(_("Error submitting destruction message"))
            else:
                with self.data:
                    del self.data["uuid"]
                    self.data["status"] = "disabled"
            finally:
                self.task.stop()
        else:
            self.log.warn(_("Unknown status: %s") % self.status)
            self.task.stop()

    def submit_exception(self, exc_info):
        t = None

        if self.status is True:
            try:
                t = traceback.format_exception(*exc_info)

                self.post(
                    self.exception_url % self.data["uuid"],
                    {
                        "traceback": "\n".join(t),
                        "type": str(exc_info[0]),
                        "value": str(exc_info[1])
                    }
                )
            finally:
                # To prevent nasty reference loops
                del exc_info, t

    def post(self, url, data):
        data = urllib.urlencode({"data": json.dumps(data)})
        req = urllib2.Request(
            url, data, {'Content-Type': 'application/json'}
        )
        return urllib2.urlopen(req).read()

    def get(self, url):
        return urllib2.urlopen(url).read()
