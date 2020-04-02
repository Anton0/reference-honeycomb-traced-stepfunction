S3_BUCKET?=reference-honeycomb-traced-stepfunction
APP_NAME?=reference-honeycomb-traced-stepfunction
OUT_FILE?=target/$(APP_NAME).zip
DELIVERABLE=$(abspath $(OUT_FILE))

VIRTUAL_ENV?=/var/venv/lambda_env
VENV_NAME?=$(VIRTUAL_ENV)
VENV_ACTIVATE=. $(VENV_NAME)/bin/activate
PYTHON=${VENV_NAME}/bin/python3

clean: ##=> Clean all the things
	@rm -f ${DELIVERABLE}
	@rm -rf dist/
	@rm -rf target/

dist: clean
	mkdir -p dist
	pip3 install --upgrade -r requirements.txt -t dist/

package: dist ##=> Build service zip
	$(info [+] Build Package")
	mkdir -p target
	cd src && zip -X -q -r9 ${DELIVERABLE} ./ -x \*__pycache__\* -x \*.git\*
	cd dist && zip -X -q -u -r9 ${DELIVERABLE} ./

deploy-stepfunction-cloudformation:
	@aws s3 mb s3://$(S3_BUCKET) || true
	@aws cloudformation package \
		--template-file cloudformation/sfn-honeycomb.yml \
		--output-template-file cloudformation/sfn-honeycomb.out.yml \
		--s3-bucket $(S3_BUCKET)

	@aws cloudformation deploy \
		--no-fail-on-empty-changeset \
		--template-file cloudformation/sfn-honeycomb.out.yml \
		--stack-name reference-honeycomb-traced-stepfunction \
		--capabilities CAPABILITY_NAMED_IAM

deploy: package deploy-stepfunction-cloudformation