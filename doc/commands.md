# Commands

This file contains a set of vital commands to handle the OEA instance correctly.


## User management

`invenio users create <email> --password <pwd> --active --confirm`

`invenio roles add <email> admin`




## Launch

### Local run

```bash
invenio-cli run
invenio-cli services setup -N -f
invenio-cli services start
invenio-cli services destroy
``` 

### Docker env

* The command first builds the application docker image and afterwards
starts the application and related services (database, Elasticsearch, Redis
and RabbitMQ). The build and boot process will take some time to complete,
especially the first time as docker images have to be downloaded during the
process: `invenio-cli containers start --lock --build --setup`


* After change in a JS / CSS file:  
`invenio-cli assets build`


## Vocabularies

* When creating a new field with the relevant vocabulary and UI, it is necessary to run `invenio rdm-records fixtures` to update the database with the new field and its vocabulary.

* Adding custom fields:  
`invenio rdm-records custom-fields init -f oea:educationLevel`

* Adding vocabularies:  
`invenio vocabularies import -f app_data/vocabularies/oea_education_level.yaml`

## Troubleshooting

### KeyError: 'video' / 'lesson' / any resource type — API returns 500

**Symptom:** `/api/records` returns HTTP 500 with a traceback ending in `KeyError: 'video'` (or another resource type) in `facets.py`.

**Cause:** The facet `label_map` cannot find the label for a resource type that exists in the OpenSearch index but not in the vocabulary loaded in the DB. This happens after partial restarts or when vocabularies were not loaded correctly.

**Quick fix (without rebuild):**

Apply the patch on the fly in the container (already included in the Dockerfile from the next build):
```bash
docker exec -it prod-web-api-1 bash
sed -i 's/"label": label_map\[key\]/"label": label_map.get(key, key)/g' /usr/local/lib/python3.9/site-packages/invenio_records_resources/services/records/facets/facets.py
kill -HUP 1
exit
```

If the problem persists after the patch, reload the vocabularies:
```bash
docker exec -it prod-web-api-1 bash
invenio rdm fixtures
invenio vocabularies import -f app_data/vocabularies/oea_education_level.yaml
invenio vocabularies import -f app_data/vocabularies/oea_discipline.yaml
exit
```

**Note:** This patch is a workaround for upstream bug [invenio-records-resources#663](https://github.com/inveniosoftware/invenio-records-resources/pull/663), not yet merged. Once a version including the fix is released, remove the related `RUN sed -i` from the `Dockerfile`.

---

### ValueError: too many values to unpack — crash on /account/settings/applications/

**Symptom:** The API key creation page (`/account/settings/applications/clients/new/`) returns HTTP 500 with `ValueError: too many values to unpack (expected 3)` in `form_styling.py`.

**Cause:** Incompatibility between WTForms 3.x and `invenio_oauth2server`: `iter_choices()` returns 4 values instead of 3.

**Quick fix (without rebuild):**
```bash
docker exec -it prod-web-ui-1 bash
sed -i 's/for val, label, selected in field.iter_choices()/for val, label, selected, *_ in field.iter_choices()/g' /usr/local/lib/python3.9/site-packages/invenio_oauth2server/theme/semantic/form_styling.py
kill -HUP 1
exit
```

---

### Corrupted static volume

1. When dealing with the `static` volume, it is necessary to wipe it somehow (just don't run docker down, but maybe docker stop). To wipe it, use `docker volume rm static_data`

---

### Hacks for M1 Mac

1. Enable `sqlalchemy = {extras = ["asyncio"]}` in Pipfile in order to be able
   to build also on M1 machine.
2. Depending on your machine architecture, there could be a problem during the local install due to the missing cairo-2 lib. I had to manually install it with `brew install cairo` and then `brew link --force cairo`.
3. This may not really solve the issue, due to a discoverability issue. So, it's possible that you will have to manually link the missing lib. To do so, run `ln -s /opt/homebrew/lib/libcairo.2.dylib .` in your folder.
4. Sometimes it may happen that during the normal install there is a problem with some python libs. As such, this is a possible solution: `ln -s /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/config-3.9-darwin /Users/<path_to_correct_folder>/.venv/lib/python3.9/config-3.9-darwin` 
