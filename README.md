# Organelle Quality Hub
A database for complete organelle genomes on GenBank and their associated quality values.

[Check it out live here.](https://organellequalityhub-prototype.onrender.com/)


## Production database deployment

The `Deploy database` GitHub Actions workflow runs Django migrations after changes are pushed to `main`.

For GitHub Actions to work, a developer needs to configure these GitHub secrets:

* `DEPLOY_HOST`: `ts-oqhub-prod.fhsu.edu`
* `DEPLOY_USER`: SSH username
* `DEPLOY_SSH_KEY`: private SSH key
* `DEPLOY_PORT`: SSH port, if not `22`

For GitHub Actions to work, a developer needs to configure `DEPLOY_PATH` as the repository’s absolute server path.

Note: The SSH user must be able to run commands as `oqhub` using `sudo -n -u oqhub` without a password prompt. Direct SSH access as `oqhub` requires adjusting the workflow.

