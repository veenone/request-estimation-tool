// PRESTO (Test Effort Estimation Tool) CI/CD pipeline.
// Builds a single image containing the FastAPI backend + NiceGUI and Streamlit
// frontends, runs the pytest suite inside the built image, then pushes to Harbor.
// Runs on either a Windows agent (PuTTY plink/pscp) or a Linux agent
// (openssh-client + sshpass). Each shell-driven stage branches on isUnix();
// the commands executed on the staging host are identical for both.
pipeline {
    agent { label 'docker-agent-01' }
    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout()
        buildDiscarder(logRotator(numToKeepStr: '20', daysToKeepStr: '14'))
    }

    parameters {
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Optional tag; defaults to git short SHA')
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Git branch to build')
        booleanParam(name: 'IS_STAGING', defaultValue: true, description: 'Tag and push the image as :staging instead of :latest (the :<IMAGE_TAG> tag is always pushed)')
        string(name: 'AGENT_LABEL', defaultValue: 'docker', description: 'Jenkins agent label. Windows agent needs PuTTY (plink/pscp); Linux agent needs openssh-client + sshpass.')
        string(name: 'SSH_HOST_STAGING', defaultValue: '10.8.8.82', description: 'Staging server IP')
        string(name: 'SSH_HOSTKEY', defaultValue: '', description: 'Windows agents only: PuTTY host key fingerprint. Linux agents use StrictHostKeyChecking=accept-new.')
        string(name: 'REGISTRY', defaultValue: 'i2j6hub1vt001.corp.idemia.com', description: 'Harbor registry')
        string(name: 'REPOSITORY', defaultValue: 'ops', description: 'Harbor project')
        string(name: 'PLINK_PATH', defaultValue: 'C:\\Program Files\\PuTTY\\plink.exe', description: 'Windows agents only: path to plink.exe')
        string(name: 'PSCP_PATH', defaultValue: 'C:\\Program Files\\PuTTY\\pscp.exe', description: 'Windows agents only: path to pscp.exe')
    }

    environment {
        REGISTRY    = "${params.REGISTRY}"
        REPOSITORY  = "${params.REPOSITORY}"
        IMAGE_NAME  = "presto"
        TAR_NAME    = "presto.tar.gz"
        SSH_HOST    = "${params.SSH_HOST_STAGING}"
        SSH_HOSTKEY = "${params.SSH_HOSTKEY}"
        PLINK       = "${params.PLINK_PATH}"
        PSCP        = "${params.PSCP_PATH}"
        REMOTE_PATH = "/home/administrator/presto-build"
        IS_STAGING  = "${params.IS_STAGING}"
    }

    stages {
        stage('Clean workspace') { steps { deleteDir() } }

        stage('Checkout presto') {
            steps {
                checkout scmGit(
                    branches: [[name: "*/${params.GIT_BRANCH}"]],
                    userRemoteConfigs: [[
                        url: 'https://i2j6serv2v0003.corp.idemia.com/Tools/presto.git',
                        credentialsId: 'achmarah'
                    ]]
                )
            }
        }

        stage('Package presto') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    script {
                        if (isUnix()) {
                            sh '''
                                tar --exclude=".git" \\
                                    --exclude="*.pyc" \\
                                    --exclude="*.pyo" \\
                                    --exclude="__pycache__" \\
                                    --exclude=".env" \\
                                    --exclude=".env.*" \\
                                    --exclude="*.pem" \\
                                    --exclude="*.key" \\
                                    --exclude="certs" \\
                                    --exclude="*.log" \\
                                    --exclude="data/*.db" \\
                                    --exclude="data/*.db-*" \\
                                    --exclude=".venv" \\
                                    --exclude=".venv2" \\
                                    --exclude="venv" \\
                                    --exclude="htmlcov" \\
                                    --exclude=".coverage" \\
                                    --exclude=".coverage.*" \\
                                    --exclude=".pytest_cache" \\
                                    --exclude=".mypy_cache" \\
                                    --exclude=".ruff_cache" \\
                                    --exclude=".idea" \\
                                    --exclude=".vscode" \\
                                    --exclude=".claude" \\
                                    --exclude=".mcp.json" \\
                                    --exclude=".gstack" \\
                                    --exclude=".remember" \\
                                    --exclude=".nicegui" \\
                                    --exclude="node_modules" \\
                                    --exclude="frontend_desktop" \\
                                    --exclude="docs" \\
                                    --exclude="sample" \\
                                    --exclude="*.whl" \\
                                    --exclude="*.tar.gz" \\
                                    -czf "/tmp/${TAR_NAME}" .
                                mv "/tmp/${TAR_NAME}" "${TAR_NAME}"
                            '''
                        } else {
                            powershell '''
                                tar --exclude=".git" `
                                    --exclude="*.pyc" `
                                    --exclude="*.pyo" `
                                    --exclude="__pycache__" `
                                    --exclude=".env" `
                                    --exclude=".env.*" `
                                    --exclude="*.pem" `
                                    --exclude="*.key" `
                                    --exclude="certs" `
                                    --exclude="*.log" `
                                    --exclude="data/*.db" `
                                    --exclude="data/*.db-*" `
                                    --exclude=".venv" `
                                    --exclude=".venv2" `
                                    --exclude="venv" `
                                    --exclude="htmlcov" `
                                    --exclude=".coverage" `
                                    --exclude=".coverage.*" `
                                    --exclude=".pytest_cache" `
                                    --exclude=".mypy_cache" `
                                    --exclude=".ruff_cache" `
                                    --exclude=".idea" `
                                    --exclude=".vscode" `
                                    --exclude=".claude" `
                                    --exclude=".mcp.json" `
                                    --exclude=".gstack" `
                                    --exclude=".remember" `
                                    --exclude=".nicegui" `
                                    --exclude="node_modules" `
                                    --exclude="frontend_desktop" `
                                    --exclude="docs" `
                                    --exclude="sample" `
                                    --exclude="*.whl" `
                                    --exclude="*.tar.gz" `
                                    -czf "$env:TEMP\\$env:TAR_NAME" .
                                Move-Item -Force "$env:TEMP\\$env:TAR_NAME" "$env:TAR_NAME"
                            '''
                        }
                    }
                }
            }
        }

        stage('Copy to staging host') {
            steps {
                retry(2) {
                    timeout(time: 5, unit: 'MINUTES') {
                        withCredentials([usernamePassword(credentialsId: '10.8.8.82_SSH_Cred', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')]) {
                            script {
                                if (isUnix()) {
                                    sh '''
                                        set +x
                                        echo "Using $SSH_USER@$SSH_HOST"
                                        export SSHPASS="$SSH_PASS"
                                        SSH_OPTS="-o StrictHostKeyChecking=accept-new"
                                        sshpass -e ssh $SSH_OPTS "$SSH_USER@$SSH_HOST" "mkdir -p $REMOTE_PATH && docker run --rm -v $REMOTE_PATH:/work python:3.12-slim sh -lc 'rm -rf /work/extracted /work/$TAR_NAME'"
                                        echo "Copying $TAR_NAME -> $SSH_USER@$SSH_HOST:$REMOTE_PATH/"
                                        sshpass -e scp $SSH_OPTS "$TAR_NAME" "$SSH_USER@$SSH_HOST:$REMOTE_PATH/"
                                    '''
                                } else {
                                    powershell '''
                                        Write-Host "Using $env:SSH_USER@$env:SSH_HOST"

                                        $plinkArgs = @('-ssh', '-batch', '-pw', $env:SSH_PASS)
                                        if ($env:SSH_HOSTKEY) { $plinkArgs = @('-hostkey', $env:SSH_HOSTKEY) + $plinkArgs }
                                        & "$env:PLINK" @plinkArgs "$env:SSH_USER@$env:SSH_HOST" "mkdir -p $env:REMOTE_PATH && docker run --rm -v ${env:REMOTE_PATH}:/work python:3.12-slim sh -lc 'rm -rf /work/extracted /work/$env:TAR_NAME'"

                                        Write-Host "Copying ${env:TAR_NAME} -> $env:SSH_USER@$env:SSH_HOST:$env:REMOTE_PATH/"
                                        $pscpArgs = @('-batch', '-pw', $env:SSH_PASS)
                                        if ($env:SSH_HOSTKEY) { $pscpArgs = @('-hostkey', $env:SSH_HOSTKEY) + $pscpArgs }
                                        & "$env:PSCP" @pscpArgs "$env:TAR_NAME" "$env:SSH_USER@${env:SSH_HOST}:$env:REMOTE_PATH/"
                                    '''
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Build image on staging host') {
            steps {
                script {
                    if (params.IMAGE_TAG?.trim()) {
                        env.EFFECTIVE_TAG = params.IMAGE_TAG.trim()
                    } else if (isUnix()) {
                        env.EFFECTIVE_TAG = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    } else {
                        env.EFFECTIVE_TAG = powershell(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    }
                }
                retry(2) {
                    timeout(time: 20, unit: 'MINUTES') {
                        withCredentials([usernamePassword(credentialsId: '10.8.8.82_SSH_Cred', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')]) {
                            script {
                                if (isUnix()) {
                                    // REMOTE_CMD lines are intentionally unindented: leading
                                    // whitespace would become part of the string sent over SSH.
                                    sh '''
                                        set +x
                                        echo "Building presto:test on $SSH_USER@$SSH_HOST"
                                        export SSHPASS="$SSH_PASS"
                                        # DOCKER_BUILDKIT=0 forces the legacy builder, which uses the
                                        # docker daemon's registry trust (/etc/docker/certs.d + system
                                        # CAs). BuildKit has its own cert pool and fails to verify the
                                        # corp Harbor CA when pulling the base image.
                                        # --network=host gives the build the host's DNS/resolver so pip
                                        # can reach the corp package index; the default bridge network
                                        # has no working resolver ("Temporary failure in name resolution").
                                        REMOTE_CMD="set -e
cd $REMOTE_PATH
mkdir -p extracted
tar -xzf $TAR_NAME -C extracted
DOCKER_BUILDKIT=0 docker build --network=host -t presto:test -f extracted/Dockerfile extracted"
                                        sshpass -e ssh -o StrictHostKeyChecking=accept-new "$SSH_USER@$SSH_HOST" "$REMOTE_CMD"
                                    '''
                                } else {
                                    powershell '''
                                        Write-Host "Building presto:test on $env:SSH_USER@$env:SSH_HOST"
                                        # DOCKER_BUILDKIT=0 forces the legacy builder, which uses the
                                        # docker daemon's registry trust; BuildKit fails to verify the
                                        # corp Harbor CA when pulling the base image.
                                        $remoteCmd = "set -e; " +
                                        "cd $env:REMOTE_PATH; " +
                                        "mkdir -p extracted; " +
                                        "tar -xzf $env:TAR_NAME -C extracted; " +
                                        "DOCKER_BUILDKIT=0 docker build --network=host -t presto:test -f extracted/Dockerfile extracted"
                                        $plinkArgs = @('-ssh', '-batch', '-pw', $env:SSH_PASS)
                                        if ($env:SSH_HOSTKEY) { $plinkArgs = @('-hostkey', $env:SSH_HOSTKEY) + $plinkArgs }
                                        & "$env:PLINK" @plinkArgs "$env:SSH_USER@$env:SSH_HOST" "$remoteCmd"
                                    '''
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Run tests on staging host') {
            steps {
                retry(2) {
                    timeout(time: 30, unit: 'MINUTES') {
                        withCredentials([usernamePassword(credentialsId: '10.8.8.82_SSH_Cred', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')]) {
                            script {
                                if (isUnix()) {
                                    // Run the pytest suite inside the BUILT image. Test deps (the
                                    // [dev] extra) are baked in at build time, so this runs OFFLINE —
                                    // the staging host has no PyPI access at `docker run` time.
                                    // --entrypoint sh bypasses the multi-process prod entrypoint
                                    // (uvicorn + Streamlit + NiceGUI).
                                    //
                                    // No env file needed: each test builds its own isolated, throwaway
                                    // SQLite database via fixtures, so no external DB/secrets are required.
                                    sh '''
                                        set +x
                                        echo "Running pytest in presto:test on $SSH_USER@$SSH_HOST"
                                        export SSHPASS="$SSH_PASS"
                                        REMOTE_CMD="set -e
docker run --rm --entrypoint sh presto:test -lc 'cd /app/backend && python -m pytest -q'"
                                        sshpass -e ssh -o StrictHostKeyChecking=accept-new "$SSH_USER@$SSH_HOST" "$REMOTE_CMD"
                                    '''
                                } else {
                                    powershell '''
                                        Write-Host "Running pytest in presto:test on $env:SSH_USER@$env:SSH_HOST"
                                        $remoteCmd = "set -e; " +
                                        "docker run --rm --entrypoint sh presto:test -lc 'cd /app/backend && python -m pytest -q'"
                                        $plinkArgs = @('-ssh', '-batch', '-pw', $env:SSH_PASS)
                                        if ($env:SSH_HOSTKEY) { $plinkArgs = @('-hostkey', $env:SSH_HOSTKEY) + $plinkArgs }
                                        & "$env:PLINK" @plinkArgs "$env:SSH_USER@$env:SSH_HOST" "$remoteCmd"
                                    '''
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Push image to Harbor') {
            steps {
                retry(2) {
                    timeout(time: 20, unit: 'MINUTES') {
                        withCredentials([
                            usernamePassword(credentialsId: 'robot$uploader', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASSWORD'),
                            usernamePassword(credentialsId: '10.8.8.82_SSH_Cred', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')
                        ]) {
                            script {
                                if (isUnix()) {
                                    // REMOTE_CMD lines are intentionally unindented: leading
                                    // whitespace would become part of the string sent over SSH.
                                    sh '''
                                        set +x
                                        echo "Pushing presto:test from $SSH_USER@$SSH_HOST"
                                        export SSHPASS="$SSH_PASS"
                                        tag="$EFFECTIVE_TAG"
                                        if [ -z "$tag" ]; then tag="latest"; fi
                                        imageRef="$REGISTRY/$REPOSITORY/$IMAGE_NAME"

                                        # Re-tag the locally-built presto:test with the real Harbor
                                        # refs. A staging build gets :staging but NOT :latest, so it
                                        # can't overwrite the production "latest" pointer.
                                        if [ "$IS_STAGING" = "true" ]; then
                                            tagCmds="docker tag presto:test ${imageRef}:$tag; docker tag presto:test ${imageRef}:staging;"
                                            pushCmds="docker push ${imageRef}:$tag; docker push ${imageRef}:staging;"
                                            echo "IS_STAGING=true -> pushing :$tag and :staging (NOT :latest)"
                                        else
                                            tagCmds="docker tag presto:test ${imageRef}:$tag; docker tag presto:test ${imageRef}:latest;"
                                            pushCmds="docker push ${imageRef}:$tag; docker push ${imageRef}:latest;"
                                        fi

                                        echo "Registry=$REGISTRY Repo=$REPOSITORY Image=$IMAGE_NAME Tag=$tag IS_STAGING=$IS_STAGING"
                                        REMOTE_CMD="set -e
printf '%s' '$HARBOR_PASSWORD' | docker login -u '$HARBOR_USER' --password-stdin $REGISTRY
$tagCmds
$pushCmds
docker logout $REGISTRY || true"
                                        sshpass -e ssh -o StrictHostKeyChecking=accept-new "$SSH_USER@$SSH_HOST" "$REMOTE_CMD"
                                    '''
                                } else {
                                    powershell '''
                                        Write-Host "Pushing presto:test from $env:SSH_USER@$env:SSH_HOST"
                                        $registry   = "$env:REGISTRY"
                                        $repo       = "$env:REPOSITORY"
                                        $image      = "$env:IMAGE_NAME"
                                        $tag        = "$env:EFFECTIVE_TAG"
                                        if (-not $tag) { $tag = "latest" }
                                        $imageRef   = "$registry/$repo/$image"

                                        # Re-tag the locally-built presto:test with the real Harbor
                                        # refs. A staging build gets :staging but NOT :latest.
                                        if ($env:IS_STAGING -eq 'true') {
                                            $tagCmds  = "docker tag presto:test ${imageRef}:$tag; docker tag presto:test ${imageRef}:staging;"
                                            $pushCmds = "docker push ${imageRef}:$tag; docker push ${imageRef}:staging;"
                                            Write-Host "IS_STAGING=true -> pushing :$tag and :staging (NOT :latest)"
                                        } else {
                                            $tagCmds  = "docker tag presto:test ${imageRef}:$tag; docker tag presto:test ${imageRef}:latest;"
                                            $pushCmds = "docker push ${imageRef}:$tag; docker push ${imageRef}:latest;"
                                        }

                                        Write-Host "Registry=$registry Repo=$repo Image=$image Tag=$tag IS_STAGING=$env:IS_STAGING"
                                        $remoteCmd = "set -e; " +
                                        "printf '%s' '$env:HARBOR_PASSWORD' | docker login -u '$env:HARBOR_USER' --password-stdin $registry; " +
                                        "$tagCmds " +
                                        "$pushCmds " +
                                        "docker logout $registry || true"
                                        $plinkArgs = @('-ssh', '-batch', '-pw', $env:SSH_PASS)
                                        if ($env:SSH_HOSTKEY) { $plinkArgs = @('-hostkey', $env:SSH_HOSTKEY) + $plinkArgs }
                                        & "$env:PLINK" @plinkArgs "$env:SSH_USER@$env:SSH_HOST" "$remoteCmd"
                                    '''
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: "${TAR_NAME}", fingerprint: true, allowEmptyArchive: true
            deleteDir()
        }
    }
}
