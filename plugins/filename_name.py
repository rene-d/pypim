import logging
from typing import List

logger = logging.getLogger("pypim")


DEPRECATED_PYTHON = set(
    [
        "3.0",
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "2.3",
        "2.4",
        "2.5",
        "2.6",
        "cp25",
        "cp26",
        "cp31",
        "cp32",
        "cp33",
        "cp34",
        "py31",
        "py32",
        "py33",
        "py34",
    ]
)


class ExcludePlatformFilter:
    """
    Filters releases based on regex patters defined by the user.
    """

    name = "exclude_platform"

    _patterns: List[str] = []
    _packagetypes: List[str] = []

    def initialize_plugin(self):
        """
        Initialize the plugin reading patterns from the config.
        """
        if self._patterns or self._packagetypes:
            logger.debug(
                "Skipping initalization of Exclude Platform plugin. "
                + "Already initialized"
            )
            return

        try:
            tags = self.configuration["blacklist"]["platforms"].split()
        except KeyError:
            logger.error(f"Plugin {self.name}: missing platforms= setting")
            return

        for platform in tags:
            lplatform = platform.lower()

            if lplatform in ("windows", "win"):
                # PEP 425
                # see also setuptools/package_index.py
                self._patterns.extend([".win32", "-win32", "win_amd64", "win-amd64"])
                # PEP 527
                self._packagetypes.extend(["bdist_msi", "bdist_wininst"])

            elif lplatform in ("macos", "macosx"):
                self._patterns.extend(["macosx_", "macosx-"])
                self._packagetypes.extend(["bdist_dmg"])

            elif lplatform in ("freebsd"):
                # concerns only very few files
                self._patterns.extend([".freebsd", "-freebsd"])

            elif lplatform in ("linux"):
                self._patterns.extend(
                    [
                        "linux-i686",  # PEP 425
                        "linux-x86_64",  # PEP 425
                        "linux_armv7l",  # https://github.com/pypa/warehouse/pull/2010
                        "linux_armv6l",  # https://github.com/pypa/warehouse/pull/2012
                        "manylinux1_",  # PEP 513
                        "manylinux2010_",  # PEP 571
                    ]
                )
                self._packagetypes.extend(["bdist_rpm"])

        logger.info(f"Initialized {self.name} plugin with {self._patterns!r}")

    def filter(self, info, releases, removed_desc=[]):
        """
        Remove files from `releases` that match any pattern.
        """
        # Make a copy of releases keys
        # as we may delete packages during iteration
        versions = list(releases.keys())
        for version in versions:
            new_files = []
            for file_desc in releases[version]:
                if self._check_match(file_desc):
                    removed_desc.append(file_desc)
                else:
                    new_files.append(file_desc)
            if len(new_files) == 0:
                del releases[version]
            else:
                releases[version] = new_files
        logger.debug(f"{self.name}: removed: {len(removed_desc)}")

    def _check_match(self, file_desc) -> bool:
        """
        Check if a release version matches any of the specificed patterns.

        Parameters
        ==========
        name: file_desc
            file description entry

        Returns
        =======
        bool:
            True if it matches, False otherwise.
        """

        python_version = file_desc.get("python_version", "")
        if python_version in DEPRECATED_PYTHON:
            return True

        # source dist: never filter out
        pt = file_desc.get("packagetype")
        if pt == "sdist":
            return False

        # Windows installer
        if pt in self._packagetypes:
            return True

        fn = file_desc["filename"]
        for i in self._patterns:
            if i in fn:
                return True

        return False
