# Commands

This file contains a set of vital commands to handle the OEA instance correctly.


## User management

`invenio users create <email> --password <pwd> --active --confirm`

`invenio roles add <email> admin`




## Launch

### Local run
invenio-cli run
invenio-cli services setup -N -f
invenio-cli services start
invenio-cli services destroy

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

### Hacks for M1 Mac

1. Enable `sqlalchemy = {extras = ["asyncio"]}` in Pipfile in order to be able
   to build also on M1 machine.
2. Depending on your machine architecture, there could be a problem during the local install due to the missing cairo-2 lib. I had to manually install it with `brew install cairo` and then `brew link --force cairo`.
3. This may not really solve the issue, due to a discoverability issue. So, it's possible that you will have to manually link the missing lib. To do so, run `ln -s /opt/homebrew/lib/libcairo.2.dylib .` in your folder.
4. Sometimes it may happen that during the normal install there is a problem with some python libs. As such, this is a possible solution: `ln -s /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/config-3.9-darwin /Users/<path_to_correct_folder>/.venv/lib/python3.9/config-3.9-darwin` 
