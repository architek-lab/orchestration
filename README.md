## Using this repo

- Clone this repo: `git clone git@github.com:architek-lab/orchestration.git`
- Change directory into orchestration
- Create python virtual environment: `python -m venv venv`
- Activate environment: `source venv/bin/activate`
- Install reuirements file: 
    - `pip install -r ci_requirements.txt`
    - `pip install -r requirements.txt`


## Setup Authentication Credentials to AWS

- Install aws-vault
    - `brew install aws-vault` on mac
    - For WSL: [download](https://sourceforge.net/projects/aws-vault.mirror/) the binary file
    - Move it to linux path: `mv <path/to/downloaded/binary-file> /usr/local/bin/aws-vault`
    - Add permission to make it executable.
        - confirm installation: `aws-vault list`
        - If there is an error to specify keychain ring, set the *backend-secret=file* and append to bash profile
            - `export AWS_VAULT_BACKEND=file >> ~/.bashrc`
            - update profile: `source ~/.bashrc`
        - More on [aws-vault](https://github.com/99designs/aws-vault)

- Add profile credentials: 
    - `aws-vault add architek-lab-dev`
    - Input AWS access key, secret access key and a passphrase to always exec into the profile
    - Confirm authentication: `aws-vault exec architek-orchestration-dev -- aws configure list`
        - You should see `access key` and `secret key` configured
