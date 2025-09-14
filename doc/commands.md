# Commands

A set of vital commands to handle the OEA instance correctly.

## Local development

It's possible to run the application locally in different ways:

1. launching `invenio` locally and installing the dependencies manually on your own machine (e.g., redis, elasticsearch, rabbitmq).
2. Using a combination of `invenio` locally and `docker-compose` (for all the other services).
3. Running all the services via docker compose.

For the sake of simplicity, we recommend using option 2. for the local development and option 3 to test a production-like environment locally.

### 2. Local `invenio` + `docker-compose`

#### Setup

The FIRST time you are setting up the local services, you need to run the following commands:
```bash
python3 -m virtualenv .venv
.source .venv/bin/activate
invenio-cli services setup -N -f
invenio-cli services start
invenio-cli run
```


#### Run 

If you have already done the setup, you don't need to run the `invenio-cli services setup -N -f` command again.
You can just run `invenio-cli services start` and `invenio-cli run` to start the services and run the application.


#### Destroy

If you want to destroy the docker services, you can run the following command:

```bash
invenio-cli services destroy
```


### Docker env

* The command first builds the application docker image and afterwards
starts the application and related services (database, Elasticsearch, Redis
and RabbitMQ). The build and boot process will take some time to complete,
especially the first time as docker images have to be downloaded during the
process: `invenio-cli containers start --lock --build --setup`




## User management

`invenio users create <email> --password <pwd> --active --confirm`

`invenio roles add <email> admin`




* After change in a JS / CSS file:  
`invenio-cli assets build`


## Vocabularies

* When creating a new field with the relevant vocabulary and UI, it is necessary to run `invenio rdm-records fixtures` to update the database with the new field and its vocabulary.

* Adding custom fields:  
`invenio rdm-records custom-fields init -f oea:educationLevel`

* Adding vocabularies:  
`invenio vocabularies import -f app_data/vocabularies/oea_education_level.yaml`

## Troubleshooting
1. When dealing with the `static` volume, it is necessary to wipe it somehow (just don't run docker down, but maybe docker stop). To wipe it, use `docker volume rm static_data`


### Hacks for M1 Mac

1. Enable `sqlalchemy = {extras = ["asyncio"]}` in Pipfile in order to be able
   to build also on M1 machine.
2. Depending on your machine architecture, there could be a problem during the local install due to the missing cairo-2 lib. I had to manually install it with `brew install cairo` and then `brew link --force cairo`.
3. This may not really solve the issue, due to a discoverability issue. So, it's possible that you will have to manually link the missing lib. To do so, run `ln -s /opt/homebrew/lib/libcairo.2.dylib .` in your folder.
4. Sometimes it may happen that during the normal install there is a problem with some python libs. As such, this is a possible solution: `ln -s /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/config-3.9-darwin /Users/<path_to_correct_folder>/.venv/lib/python3.9/config-3.9-darwin` 
