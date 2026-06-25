// PRESTO (Test Effort Estimation Tool) CI/CD pipeline.
//
// Builds a single image (FastAPI backend + NiceGUI + Streamlit frontends)
// directly on the Jenkins agent (docker-agent-01), runs the pytest suite inside
// the built image, then pushes to Harbor. The agent has corp-network access to
// the Nexus PyPI mirror and the Harbor registry, so no staging-host SSH hop is
// needed for the build.
pipeline {
    agent { label 'docker1' }
    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout()
        buildDiscarder(logRotator(numToKeepStr: '20', daysToKeepStr: '14'))
    }

    parameters {
        string(name: 'IMAGE_TAG', defaultValue: '', description: 'Optional image tag; defaults to the git short SHA')
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Git branch to build')
        booleanParam(name: 'IS_STAGING', defaultValue: true, description: 'Tag and push the image as :staging instead of :latest (the :<IMAGE_TAG> tag is always pushed)')
        string(name: 'REGISTRY', defaultValue: 'i2j6hub1vt001.corp.idemia.com', description: 'Harbor registry')
        string(name: 'REPOSITORY', defaultValue: 'ops', description: 'Harbor project')
    }

    environment {
        REGISTRY   = "${params.REGISTRY}"
        REPOSITORY = "${params.REPOSITORY}"
        IMAGE_NAME = "presto"
        IS_STAGING = "${params.IS_STAGING}"
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

        stage('Build image') {
            steps {
                script {
                    env.EFFECTIVE_TAG = params.IMAGE_TAG?.trim() ?:
                        sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                }
                timeout(time: 25, unit: 'MINUTES') {
                    // DOCKER_BUILDKIT=0: the legacy builder uses the daemon's registry trust
                    // (/etc/docker/certs.d + system CAs) to pull the corp Harbor base image;
                    // BuildKit has its own cert pool and fails to verify the corp CA.
                    // --network=host gives the build the host resolver so pip can reach the
                    // Nexus mirror (the default bridge network has no working DNS in this env).
                    sh '''
                        set -e
                        echo "Building presto:test on agent $(hostname) (tag $EFFECTIVE_TAG)"
                        DOCKER_BUILDKIT=0 docker build --network=host -t presto:test .
                    '''
                }
            }
        }

        stage('Run tests') {
            steps {
                timeout(time: 30, unit: 'MINUTES') {
                    // Test deps (the [dev] extra) are baked into the image at build time, so
                    // pytest runs without any network. --entrypoint sh bypasses the prod
                    // multi-process entrypoint (uvicorn + Streamlit + NiceGUI). Each test
                    // builds its own throwaway SQLite DB via fixtures — no external services.
                    sh '''
                        set -e
                        echo "Running pytest inside presto:test"
                        docker run --rm --entrypoint sh presto:test -lc 'cd /app/backend && python -m pytest -q'
                    '''
                }
            }
        }

        stage('Push image to Harbor') {
            steps {
                retry(2) {
                    timeout(time: 20, unit: 'MINUTES') {
                        withCredentials([usernamePassword(credentialsId: 'robot$uploader', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASSWORD')]) {
                            // A staging build gets :<tag> and :staging but NOT :latest, so it
                            // cannot overwrite the production "latest" pointer.
                            sh '''
                                set +x
                                tag="$EFFECTIVE_TAG"
                                if [ -z "$tag" ]; then tag="latest"; fi
                                imageRef="$REGISTRY/$REPOSITORY/$IMAGE_NAME"
                                echo "Pushing $imageRef:$tag (IS_STAGING=$IS_STAGING)"

                                printf '%s' "$HARBOR_PASSWORD" | docker login -u "$HARBOR_USER" --password-stdin "$REGISTRY"
                                docker tag presto:test "${imageRef}:${tag}"
                                if [ "$IS_STAGING" = "true" ]; then
                                    docker tag presto:test "${imageRef}:staging"
                                    docker push "${imageRef}:${tag}"
                                    docker push "${imageRef}:staging"
                                else
                                    docker tag presto:test "${imageRef}:latest"
                                    docker push "${imageRef}:${tag}"
                                    docker push "${imageRef}:latest"
                                fi
                                docker logout "$REGISTRY" || true
                            '''
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            // Free the agent: drop the local images this build created.
            sh '''
                imageRef="$REGISTRY/$REPOSITORY/$IMAGE_NAME"
                docker rmi presto:test \
                    "${imageRef}:${EFFECTIVE_TAG:-latest}" \
                    "${imageRef}:staging" \
                    "${imageRef}:latest" 2>/dev/null || true
            '''
            deleteDir()
        }
    }
}
