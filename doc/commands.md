# Commands

A set of vital commands to handle the OEA instance correctly.

---

## TL;DR — just use `make`

```bash
make local    # every day: checks + start services + run app
make setup    # first time only (or after a destroy)
make stop     # stop services (data preserved)
make destroy  # nuclear option — destroys all data
make assets   # rebuild frontend after CSS/JS changes
make check    # verify all tools are installed correctly
```

Run `make help` for the full list.

---

## Local development

It's possible to run the application locally in different ways:

1. Launching `invenio` locally and installing the dependencies manually on your own machine (e.g., redis, opensearch, rabbitmq).
2. **Using a combination of `invenio` locally and `docker-compose` for all the other services. (Recommended)**
3. Running all the services via docker compose (to test a production-like environment locally).

---

## Option 2 — Local `invenio` + `docker-compose` (Recommended)

This is the standard workflow for day-to-day development.

### Prerequisites

The versions below are the ones required/tested with **InvenioRDM 12.0.10** (the version used by this project).

#### Python 3.9 — via pyenv (recommended)

Using pyenv avoids conflicts with the system Python and makes it trivial to switch versions.

```bash
# Install pyenv (macOS)
brew install pyenv

# Add to your shell (add these lines to ~/.zshrc or ~/.bashrc)
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Reload shell
source ~/.zshrc   # or source ~/.bashrc

# Install Python 3.9 and set it as the local version for this project
pyenv install 3.9   # installs the latest 3.9.x available
pyenv local 3.9     # creates a .python-version file in the project root

# Verify
python --version   # must print Python 3.9.x
```

> **Why 3.9?** InvenioRDM 12 supports Python 3.9, 3.11, and 3.12.
> This project pins to **3.9** in `Pipfile`. Do not use a different version
> or the dependency resolution will fail.

#### Node.js 18+ — via nvm (recommended)

Using nvm avoids conflicts with any system-installed Node and allows pinning the version.

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Reload shell
source ~/.zshrc   # or source ~/.bashrc

# Install and use Node.js LTS (minimum version 18, required by InvenioRDM 12)
nvm install --lts
nvm use --lts
nvm alias default --lts   # make LTS the default for new shells

# Verify
node --version   # must print v18.x.x or higher
npm --version
```

#### Docker >= 20.10.10

```bash
# Verify
docker --version          # must print 20.10.10 or higher
docker compose version    # must print v2.x.x
```

Install from https://docs.docker.com/desktop/ if not present.
Make sure Docker Desktop is **running** before executing any `invenio-cli` command.

#### invenio-cli

Install it in your **global** Python environment (outside the virtualenv), so it
is always available:

```bash
pip install invenio-cli

# Verify
invenio-cli --version
```

#### Cairo graphics library

Required for PDF badge generation. Install once at the system level:

```bash
# macOS
brew install cairo

# Ubuntu/Debian
sudo apt-get install libcairo2-dev
```

See the Apple Silicon section below if you are on M1/M2/M3.

---

### First-time setup

Run these commands once when you clone the repository or after a full `services destroy`.

```bash
# 1. Create and activate the Python 3.9 virtual environment
python3.9 -m virtualenv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install --upgrade pip
pipenv install

# 3. Set up Docker services (DB, OpenSearch, Redis, RabbitMQ)
#    -N skips demo data, -f forces a clean setup
invenio-cli services setup -N -f

# 4. Start the Docker services
invenio-cli services start

# 5. Run the application
invenio-cli run
```

The application will be available at: **https://127.0.0.1:5000**

> Note: the development server uses a self-signed certificate, so your browser
> will show a security warning. Accept it to proceed.

---

### Creating the admin user (first time only)

After the first setup, create at least one admin user:

```bash
# Make sure the virtualenv is active and services are running
invenio users create <email> --password <password> --active --confirm
invenio roles add <email> admin
```

---

### Daily workflow — starting the application

Once the first-time setup is done, this is all you need each time:

```bash
# 1. Activate the virtualenv
source .venv/bin/activate

# 2. Start Docker services
invenio-cli services start

# 3. Run the application
invenio-cli run
```

To stop everything:

```bash
# Stop the application: Ctrl+C in the terminal running invenio-cli run

# Stop Docker services (data is preserved)
invenio-cli services stop
```

---

### Stopping vs Destroying services

| Command | Effect | Data preserved? |
|---|---|---|
| `invenio-cli services stop` | Stops containers | Yes |
| `invenio-cli services destroy` | Stops and removes containers and volumes | **No** |

Use `destroy` only when you want a completely clean slate. After destroy you will need to run the full first-time setup again.

---

### Rebuilding assets (after CSS/JS changes)

If you modify any file under `assets/` or `site/openeduarchive/assets/`:

```bash
invenio-cli assets build
```

---

### Vocabularies and custom fields

Run these after a clean setup or when vocabulary definitions change:

```bash
# Load all default fixtures and vocabularies
invenio rdm-records fixtures

# Initialise custom fields
invenio rdm-records custom-fields init -f oea:educationLevel
invenio rdm-records custom-fields init -f oea:discipline

# Import custom vocabulary files
invenio vocabularies import -f app_data/vocabularies/oea_education_level.yaml
```

---

## Option 3 — Full Docker environment

Use this to test a production-like environment locally.

```bash
invenio-cli containers start --lock --build --setup
```

The build and boot process will take several minutes the first time, as Docker images need to be pulled and built.

---

## Troubleshooting

### Application does not start after stopping containers

Make sure you start services before running the application:

```bash
invenio-cli services start
invenio-cli run
```

### Stale `static` volume causes errors

Never use `docker compose down` — it removes volumes including `static_data`.
If the volume is in a broken state, remove it explicitly:

```bash
docker volume rm static_data
```

Then rebuild assets:

```bash
invenio-cli assets build
```

### Port conflicts

If ports 5432, 6379, 5672, or 9200 are already in use on your machine,
stop the conflicting services or change the port mappings in `docker-services.yml`.

---

### Notes for Apple Silicon (M1/M2/M3)

1. **SQLAlchemy asyncio extra**: the `sqlalchemy = {extras = ["asyncio"]}` line
   in `Pipfile` is required for M1/ARM builds. It is already included — do not
   remove it.

2. **Cairo library**: install it with Homebrew and force-link it:

   ```bash
   brew install cairo
   brew link --force cairo
   ```

3. **Cairo not discoverable**: if the install still fails with a missing
   `libcairo` error, manually symlink the library into the project folder:

   ```bash
   ln -s /opt/homebrew/lib/libcairo.2.dylib .
   ```

4. **Python config path error**: if you get an error about a missing
   `config-3.9-darwin` directory during the install:

   ```bash
   ln -s /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/config-3.9-darwin \
         .venv/lib/python3.9/config-3.9-darwin
   ```
