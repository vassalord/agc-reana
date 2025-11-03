#!/usr/bin/env bash

WORKFLOWNAME=$1

# Start worklow
reana-client run -w $WORKFLOWNAME

while :; do

  # Wait until the execution finishes or fails
  while :; do
    status=$(reana-client status -w $WORKFLOWNAME --json | jq -Sr '.[].status')
    if [ "$status" == "queued" ] || [ "$status" == "pending" ] || [ "$status" == "running" ]; then
      sleep 15
    else
      break
    fi
  done

  if [ "$status" == "finished" ]; then
    # Success; we can stop
    break
  else
    # Some samples failed; remove those and restart workflow (ANALYSIS SPECIFIC REQUIREMENTS)
    reana-client ls -w $WORKFLOWNAME | grep "histograms/hist_result_" | awk '{if ( $2 == 0 ) print $1;}' > errors.txt
    cat errors.txt
    while read -r badsample; do
      reana-client rm -w $WORKFLOWNAME "$badsample"
    done <errors.txt
    rm errors.txt
    reana-client restart -w $WORKFLOWNAME
  fi

done