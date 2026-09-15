import {Config} from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Captions render fine at concurrency 1; raise it if your machine is strong.
Config.setConcurrency(1);
