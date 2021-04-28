import * as functions from "firebase-functions";
import fetch from "node-fetch";

export const gcpBuildTriggerDiscord = functions.pubsub
    .topic("cloud-builds")
    .onPublish(async (pubSubEvent) => {
        console.log(pubSubEvent.data);
        const build = JSON.parse(
            Buffer.from(pubSubEvent.data, "base64").toString()
        );
        try {
            if (sendMessage(build)) {
                const msg = createBuildMessage(build);
                sendDiscordBuildPost(msg);
            }
        } catch (err) {
            console.log(err);
        }
    });

const sendMessage = (build: GoogleCloudBuild) => {
    const status = ["SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT"];
    if (status.indexOf(build.status) === -1) {
        console.log("Status not found");
        return false;
    }

    if (build.substitutions["_SERVICE_NAME"] != "vaccinate") {
        console.log("Wrong project");
        return false;
    }

    if (
        build.substitutions["_DEPLOY"] == "staging" &&
        build.status == "SUCCESS"
    ) {
        // Skip successes for staging builds, they're frequent.
        return false;
    }
    return true;
};

const sendDiscordBuildPost = async (body: Record<string, unknown>) => {
    console.log("Calling Discord with", JSON.stringify(body));
    await fetch(functions.config().discord.build_hook, {
        body: JSON.stringify(body),
        method: "POST",
        headers: { "Content-Type": "application/json" },
    });
    return true;
};

const createBuildMessage = (build: GoogleCloudBuild) => {
    const embeds: Embed[] = [];
    const msg = {
        content: "",
        embeds: embeds,
    };
    const deploy = build.substitutions["_DEPLOY"];
    const commit = build.substitutions["COMMIT_SHA"];
    const logUrl = build.logUrl;
    if (build && build.status != "SUCCESS") {
        if (build.steps) {
            for (const step of build.steps) {
                if (step.status && step.status != "SUCCESS") {
                    embeds.push({
                        title: `Deploy of ${deploy} failed in step: ${step.id}`,
                        description: `[Deploy ${step.status}](${logUrl}) of commit [${commit}](https://github.com/CAVaccineInventory/vial/commit/${commit}) in step ${step.id}.`,
                        color: 0xff0b0b,
                        timestamp: build.finishTime.toString(),
                    });
                    break;
                }
            }
        }
        if (embeds == []) {
            embeds.push({
                title: `Deploy of ${deploy} failed`,
                description: `[Deploy ${build.status}](${logUrl}) of commit [${commit}](https://github.com/CAVaccineInventory/vial/commit/${commit}).`,
                color: 0xff0b0b,
                timestamp: build.finishTime.toString(),
            });
        }
    } else {
        embeds.push({
            title: `Deploy to ${deploy} successful`,
            description: `[Deploy](${logUrl}) of commit [${commit}](https://github.com/CAVaccineInventory/vial/commit/${commit}) completed.`,
            color: 0x64ff33,
            timestamp: build.finishTime.toString(),
        });
    }
    return msg;
};

export interface Embed {
    title?: string;
    description?: string;
    color?: number;
    timestamp?: string;
}

export interface GoogleCloudBuild {
    id: string;
    projectId: string;
    status: string;
    steps?: Step[];
    createTime: Date;
    startTime: Date;
    finishTime: Date;
    buildTriggerId: string;
    options: Options;
    logUrl: string;
    substitutions: { [key: string]: string };
}

export interface Options {
    substitutionOption?: string;
    logging?: string;
}

export interface Step {
    id?: string;
    name: string;
    args: string[];
    entrypoint: string;
    timing: Timing;
    pullTiming: Timing;
    status: string;
}

export interface Timing {
    startTime: Date;
    endTime: Date;
}
