import irc3
import irc3.rfc
from datetime import datetime, timedelta

from darksouls import DSNode, DSCMNode

NODE_TTL = timedelta(minutes=5)
PUBLISH_TTL = timedelta(minutes=3)
CHANNEL = "#DSCM-Main"


@irc3.plugin
class MyPlugin:
    requires = [
        'irc3.plugins.core',
    ]

    def __init__(self, bot):
        self.bot = bot
        self.bot.nodes = dict()
        self.last_seen = dict()
        self.last_expire = datetime.utcnow()

    def connection_made(self):
        """triggered when connection is up"""

    def server_ready(self):
        """triggered after the server sent the MOTD (require core plugin)"""

    def connection_lost(self):
        """triggered when connection is lost"""

    @irc3.event(irc3.rfc.PRIVMSG)
    def on_message(self, mask, target, data, **kw):
        try:
            msg_type, msg = data.split('|', 1)
        except ValueError:
            return
        if msg_type in ["REPORT", "REPORTSELF"]:
            try:
                name, steamid, sl, phantom_type, mp_zone, world, *rest = msg.split(',')
                if rest:
                    covenant, indictments = rest
                else:
                    if steamid in self.bot.nodes and hasattr(self.bot.nodes[steamid], 'covenant'):
                        covenant = self.bot.nodes[steamid].covenant
                        indictments = self.bot.nodes[steamid].indictments
                    else:
                        covenant, indictments = None, None
            except ValueError:
                pass
            else:
                if covenant is not None:
                    node = DSCMNode(steamid, name, int(sl), int(phantom_type),
                                    int(mp_zone), world, int(covenant), int(indictments))
                else:
                    node = DSNode(steamid, name, int(sl), int(phantom_type),
                                  int(mp_zone), world)
                self.bot.nodes[steamid] = node
                self.last_seen[steamid] = datetime.utcnow()
        if (datetime.utcnow() - self.last_expire).total_seconds() > 10:
            self.expire_nodes()

    def expire_nodes(self):
        now = datetime.utcnow()
        for steamid, last in list(self.last_seen.items()):
            if (now - last) > NODE_TTL:
                del self.last_seen[steamid]
                del self.bot.nodes[steamid]
        self.last_expire = now

    @irc3.extend
    def publish_nodes(self, nodes):
        now = datetime.utcnow()
        for node in nodes:

            if (isinstance(node, DSNode) and
                    node.steamid in self.last_seen and
                    (now - self.last_seen[node.steamid]) < PUBLISH_TTL):
                continue
            clean_name = node.name.replace('|', '').replace(',', '')
            info = [clean_name, node.steamid, node.sl, node.phantom_type,
                    node.mp_zone, node.world]
            if hasattr(node, 'covenant'):
                info.extend([node.covenant, node.indictments])
            msg = "REPORT|" + ",".join(str(x) for x in info)
            self.bot.privmsg(CHANNEL, msg)


class Client:
    def __init__(self, event_loop):
        config = dict(
            nick='server-bot', autojoins=[CHANNEL],
            host='dscm.wulf2k.ca', port=8123, ssl=False,
            loop=event_loop,
            includes=['irc3.plugins.core',
                      __name__],
        )
        self.bot = irc3.IrcBot.from_config(config)
        self.bot.run(forever=False)

    @property
    def nodes(self):
        return self.bot.nodes

    def publish_nodes(self, *args, **kwargs):
        self.bot.publish_nodes(*args, **kwargs)
