import logging
from packaging.version import parse, InvalidVersion


logger = logging.getLogger(__name__)


def parse_conditions(conditions):
    """
    """

    mandatories = set()

    if conditions is None:
        return mandatories

    for cond in conditions:
        for test in cond.split(","):
            test = test.strip()
            test = test.replace("'", "")
            test = test.replace('"', "")
            if test.startswith("=="):
                if test.find("*") == -1:
                    try:
                        parse(test[2:])
                        mandatories.add(test[2:])
                        break
                    except InvalidVersion:
                        # version mal ficelée
                        pass

            # try:
            #     if t.startswith(">="): Version(t[2:])
            #     elif t.startswith(">"): Version(t[1:])
            #     elif t.startswith("<="): Version(t[2:])
            #     elif t.startswith("<"): Version(t[1:])
            #     elif t.startswith("!="): Version(t[2:])
            #     elif t.startswith("~="): Version(t[2:])
            #     else:
            #         raise Exception
            # except Exception:
            #     print("==============", k, t)

    return mandatories


class LatestReleaseFilter:
    """
    Plugin to download only latest releases
    """

    name = "latest_release"
    keep = 0  # by default, keep 'em all

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        if self.keep:
            return

        try:
            self.keep = int(self.configuration["latest_release"]["keep"])
        except KeyError:
            return
        except ValueError:
            return
        if self.keep > 0:
            logger.info(f"Initialized latest releases plugin with keep={self.keep}")

    def filter(self, info, releases, conditions=None):
        """
        Keep the latest releases
        """

        if self.keep == 0:
            return

        mandatories = parse_conditions(conditions)

        versions = list(releases.keys())
        before = len(versions)

        if before <= self.keep:
            # not enough releases: do nothing
            return

        versions_pair = sorted(map(lambda v: (parse(v), v), versions), reverse=True)

        latest = list()
        for i, v in enumerate(versions_pair):
            v = v[1]
            if i < self.keep:
                latest.append(v)
            else:
                if v in mandatories:
                    latest.append(v)

        current_version = info.get("version")
        if current_version and (current_version not in latest):
            # never remove the stable/official version
            latest[0] = current_version

        after = len(latest)
        latest = set(latest)
        for version in list(releases.keys()):
            if version not in latest:
                del releases[version]

        logger.debug(f"{self.name}: {versions} -> {latest} removed: {before - after}")
