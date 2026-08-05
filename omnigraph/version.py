"""
Created on 2025-05-28

@author: wf
"""

from basemkit.yamlable import lod_storable

import omnigraph


@lod_storable
class Version:
    """
    Version handling for nicegui widgets
    """

    name = "omnigraph"
    version = omnigraph.__version__
    date = "2025-11-01"
    updated = "2026-08-05"
    description = "Unified Python interface for multiple graph databases"

    authors = "Wolfgang Fahl"

    doc_url = "https://wiki.bitplan.com/index.php/pyomnigraph"
    chat_url = "https://github.com/WolfgangFahl/pyomnigraph/discussions"
    cm_url = "https://github.com/WolfgangFahl/pyomnigraph"

    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    # a generic user agent is rejected by the wikidata endpoint
    user_agent = f"{name}/{version} ({cm_url}) python-requests"

    license = f"""Copyright 2025 contributors. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied."""

    longDescription = f"""{name} version {version}
{description}

  Created by {authors} on {date} last updated {updated}"""
