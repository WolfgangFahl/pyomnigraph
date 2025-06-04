# omnigraph
[![pypi](https://img.shields.io/pypi/pyversions/pyomnigraph)](https://pypi.org/project/pyomnigraph/)
[![Github Actions Build](https://github.com/WolfgangFahl/pyomnigraph/actions/workflows/build.yml/badge.svg)](https://github.com/WolfgangFahl/pyomnigraph/actions/workflows/build.yml)
[![PyPI Status](https://img.shields.io/pypi/v/pyomnigraph.svg)](https://pypi.python.org/pypi/pyomnigraph/)
[![GitHub issues](https://img.shields.io/github/issues/WolfgangFahl/pyomnigraph.svg)](https://github.com/WolfgangFahl/pyomnigraph/issues)
[![GitHub closed issues](https://img.shields.io/github/issues-closed/WolfgangFahl/pyomnigraph.svg)](https://github.com/WolfgangFahl/pyomnigraph/issues/?q=is%3Aissue+is%3Aclosed)
[![API Docs](https://img.shields.io/badge/API-Documentation-blue)](https://WolfgangFahl.github.io/pyomnigraph/)
[![License](https://img.shields.io/github/license/WolfgangFahl/pyomnigraph.svg)](https://www.apache.org/licenses/LICENSE-2.0)


Unified Python interface for multiple graph databases

## Docs and Tutorials
[Wiki](https://wiki.bitplan.com/index.php/pyomnigraph)

## Motivation

## Examples
```bash
omnigraph --list-servers -df github
```
| Name                                | Container Name       | Wikidata                                               | Image                                                                                            |   Port |   Test Port | Dataset   | Active   | User   |
|-------------------------------------|----------------------|--------------------------------------------------------|--------------------------------------------------------------------------------------------------|--------|-------------|-----------|----------|--------|
| [blazegraph](http://localhost:9898) | blazegraph-omnigraph | [Q20127748](https://www.wikidata.org/wiki/Q20127748)   | [lyrasis/blazegraph:2.1.5](https://hub.docker.com/r/lyrasis/blazegraph)                          |   9898 |        7898 | kb        | ✓        |        |
| [jena](http://localhost:3030)       | jena-omnigraph       | [Q109376461](https://www.wikidata.org/wiki/Q109376461) | [stain/jena-fuseki:latest](https://hub.docker.com/r/stain/jena-fuseki)                           |   3030 |        7030 | ds        | ✓        | admin  |
| [qlever](http://localhost:7019)     | qlever-omnigraph     | [Q111016295](https://www.wikidata.org/wiki/Q111016295) | [adfreiburg/qlever:latest](https://hub.docker.com/r/adfreiburg/qlever)                           |   7019 |        7819 | olympics  | ✓        |        |
| [virtuoso](http://localhost:8890)   | virtuoso-omnigraph   | [Q7935239](https://www.wikidata.org/wiki/Q7935239)     | [openlink/virtuoso-opensource-7:latest](https://hub.docker.com/r/openlink/virtuoso-opensource-7) |   8890 |        8390 | KB        | ✓        | dba    |

### Server Management

```bash
# Start specific servers
omnigraph -s jena --cmd start

# Restart sequence - stop remove and start
omnigraph -s jena --cmd stop rm start

# Start all configured servers
omnigraph -s all --cmd start

# Check server status
omnigraph -s blazegraph --cmd status

# Open web ui
omnigraph -s jena --cmd webui
```

### Data Operations

```bash
# Load datasets
omnigraph -s blazegraph --cmd load

# Get triple count
omnigraph -s blazegraph --cmd count

# Use test environment
omnigraph --test -s blazegraph --cmd start load
```

## Usage
### omnigraph command line
```bash
omnigraph -h
usage: omnigraph [-h] [-a] [-d] [-ds DATASETS [DATASETS ...]] [-dc DATASETS_CONFIG] [-f] [-r {turtle,rdf-xml,n3,json-ld}] [-q] [-V] [--apache APACHE]
                 [-c CONFIG] [--cmd CMD [CMD ...]] [-df DOC_FORMAT] [-l] [--test] [-s SERVERS [SERVERS ...]] [-v]

Unified Python interface for multiple graph databases

options:
  -h, --help            show this help message and exit
  -a, --about           show about info [default: False]
  -d, --debug           show debug info [default: False]
  -ds DATASETS [DATASETS ...], --datasets DATASETS [DATASETS ...]
                        datasets to work with - all is an alias for all datasets [default: ['wikidata_triplestores']]
  -dc DATASETS_CONFIG, --datasets-config DATASETS_CONFIG
                        Path to datasets configuration YAML file [default: /Users/wf/Library/Python/3.12/lib/python/site-
                        packages/omnigraph/resources/examples/datasets.yaml]
  -f, --force           force actions that would modify existing data [default: False]
  -r {turtle,rdf-xml,n3,json-ld}, --rdf_format {turtle,rdf-xml,n3,json-ld}
                        RDF format to use [default: turtle]
  -q, --quiet           avoid any output [default: False]
  -V, --version         show program's version number and exit
  --apache APACHE       create apache configuration file for the given server(s)
  -c CONFIG, --config CONFIG
                        Path to server configuration YAML file [default: /Users/wf/Library/Python/3.12/lib/python/site-
                        packages/omnigraph/resources/examples/servers.yaml]
  --cmd CMD [CMD ...]   commands to execute on servers: bash, clear, count, info, load, logs, needed, rm, start, status, stop, webui
  -df DOC_FORMAT, --doc-format DOC_FORMAT
                        The document format to use [default: plain]
  -l, --list-servers    List available servers [default: False]
  --test                use test environment [default: False]
  -s SERVERS [SERVERS ...], --servers SERVERS [SERVERS ...]
                        servers to work with - 'all' selects all configured servers [default: ['blazegraph']]
  -v, --verbose         show verbose output [default: False]
```

### rdfdump command line
```bash
rdfdump -h
usage: rdfdump [-h] [-a] [-d] [-ds DATASETS [DATASETS ...]] [-dc DATASETS_CONFIG] [-f] [-r {turtle,rdf-xml,n3,json-ld}] [-q] [-V] [--limit LIMIT] [-l]
               [--count] [--dump] [-4o] [--max-count MAX_COUNT] [--no-progress] [--output-path OUTPUT_PATH] [--tryit]

Unified Python interface for multiple graph databases

options:
  -h, --help            show this help message and exit
  -a, --about           show about info [default: False]
  -d, --debug           show debug info [default: False]
  -ds DATASETS [DATASETS ...], --datasets DATASETS [DATASETS ...]
                        datasets to work with - all is an alias for all datasets [default: ['wikidata_triplestores']]
  -dc DATASETS_CONFIG, --datasets-config DATASETS_CONFIG
                        Path to datasets configuration YAML file [default: /Users/wf/Library/Python/3.12/lib/python/site-
                        packages/omnigraph/resources/examples/datasets.yaml]
  -f, --force           force actions that would modify existing data [default: False]
  -r {turtle,rdf-xml,n3,json-ld}, --rdf_format {turtle,rdf-xml,n3,json-ld}
                        RDF format to use [default: turtle]
  -q, --quiet           avoid any output [default: False]
  -V, --version         show program's version number and exit
  --limit LIMIT         Number of triples per request [default: 10000]
  -l, --list            List available datasets [default: False]
  --count               List available datasets with triple counts[default: False]
  --dump                perform the dump [default: False]
  -4o, --for-omnigraph  store dump at default omnigraph location [default: False]
  --max-count MAX_COUNT
                        Maximum number of solutions/triples to download (uses dataset expected_solutions if not specified)
  --no-progress         Disable progress bar
  --output-path OUTPUT_PATH
                        Path for dump files
  --tryit               open the try it! URL [default: False]
``