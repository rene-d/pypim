from collections import defaultdict
import logging


logger = logging.getLogger("pypim")


# packages too big or updated too frequently
TOOFAT = [
    "cupy",
    "cupy-%",  # CuPy : NumPy-like API accelerated with CUDA
    "mxnet",
    "mxnet-%",  # Apache MXNet is a deep learning framework
    "tf-nightly%",  # nightly TensorFlow
]

# threats detected by Kaspersky
THREATS = [
    "Cuckoo",
    "secret_miner",
    "androwarn",
    "thug",
    "gpgmailencrypt",
    "crackmapexec",
    "escposprinter",
    "kayobe",
    "kalabash-amavis",
    "modoboa_amavis",
    "avocado-framework-plugin-vt",
    "grr-response-test",
    "modoboa-amavis",
    "edeposit.amqp.antivir",
    "jabbercracky",
    "ecxclient",
    "test-typo-pypi",
    "rigpy",
    "vxstreamlib",
    "Pythonic",
    "formasaurus",
    "pytagora",
    "pytagora2",
    "plainbox",
    "duxlot",
    "babysploit",
    "manim",
    "csirtg_mail",
    "lda",
    "scrapyc",
]

SCAM = [
    # useless when offline
    "aws%",
    "azure%",
    "cmsplugin%",
    "github%",
    "google-cloud%",
    "mastercard%",
    # bullshit (among tons not listed...)
    "0",
    "0-._.-._.-._.-._.-._.-._.-0" "0.0.1",
    "0-core-client",
    "aliyun%",
    "nester%",
    "raptus%",
    "Bravo",
    # requirements badly written
    "pcu",
    "bareasgi-cors",
    "bareasgi-graphql-next",
    "candid",
    "wechat-mchpay",
    "eGo",
    "Flask-Z3950",
]


def get_blacklist(db):
    """
    """

    blacklist = set()
    reason = defaultdict(list)

    def filter(title, *requests):
        nonlocal blacklist
        excluded = set()
        for sql in requests:
            logger.debug(f"sql: {sql}")
            excluded = excluded.union(set(name for name, in db.execute(sql).fetchall()))
        for name in excluded:
            reason[name].append(title)
        blacklist = blacklist.union(excluded)
        logger.info(f"{title:>20}: {len(excluded):6}   blacklist:{len(blacklist):6}")

    # remove ignored packaged (packages without release)
    filter("ignored", "select name from list_packages where ignore")

    # remove packaged listed in TOOFAT
    sql = "select name from list_packages where 0=1"
    sql += "\n".join(f' or name like "{pattern}"' for pattern in TOOFAT)
    filter("toobig", sql)

    # remove packaged listed in THREATS
    sql = "select name from list_packages where 0=1"
    sql += "\n or name in (" + ",".join(f'"{thread}"' for thread in THREATS) + ")"
    filter("threats", sql)

    # remove packaged listed in SCAM
    sql = "select name from list_packages where 0=1"
    sql += "\n".join(f' or name like "{pattern}"' for pattern in SCAM)
    filter("scam", sql)

    # remove Plone (CMS), Django (web), Odoo (ERP) : too many packages
    filter(
        "Framework :: Plone",
        "select distinct name from classifier where classifier like 'Framework :: Plone%'",
        "select name from list_packages where name like 'Products.%' or name like 'collective.%'",
    )

    filter(
        "Framework :: Django",
        "select distinct name from classifier where classifier like 'Framework :: Django'",
        "select name from list_packages where name like 'django%'",
    )

    filter(
        "Framework :: Odoo",
        "select distinct name from classifier where classifier like 'Framework :: Odoo'",
        "select name from list_packages where name like 'odoo%'",
    )

    # remove packages without file
    filter(
        "without file",
        "select name from package where name not in (select distinct name from file)",
    )

    # filter("description UNKNOWN", 'select name from package where description="UNKNOWN"')
    # filter("missing description", 'select name from package where description=""')
    # sql = 'select name from package '
    # sql += 'where (description="" or description="UNKNOWN" or description is null)'
    # sql += '  and (summary="" or summary="UNKNOWN" or summary is null)'
    # filter("bad description", sql)

    # filter(f"upload_time < {MIN_DATE}",
    #        f'select name from file group by name having max(upload_time) < "{MIN_DATE}"')

    return blacklist, reason
