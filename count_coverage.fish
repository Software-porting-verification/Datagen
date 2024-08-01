#!/usr/bin/env fish

####################################################
#
#
# Download built packages and count their test coerage.
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################


## collect coverage reports

if test (count $argv) -ne 1
    echo Please provide a dir!
end

set OSC osc

mkdir $argv[1]
cd    $argv[1]

# get the successfully built pkgs
for i in ($OSC results openEuler:24.03:Perf-Coverage --csv | grep -E 'succeeded$' | cut -d';' -f 1)
    # download the artifacts
    $OSC getbinaries openEuler:24.03:Perf-Coverage $i openEuler_24.03_RVPT_standard x86_64
end

fd tar.gz -x mv {} .
rm -rf binaries
mkdir -p tars
fd tar.gz -x mv {} tars
cd tars
fd tar.gz -x tar axf {}
# rm *.tar.gz

set TEMP (pwd)/temp_cov_(date +%N_%F_%T)

for i in PERF_COV_*
    pushd $i/coverage

    # calculate avg function and line coverage
    if test -e all.report
        set result (grep TOTAL all.report)
        if test $status -eq 0
            set nums (echo $result | awk -e '{print $7 ":" $10}')
            set ns (string split : $nums)
            set func_cov (string trim --right --chars % $ns[1])
            set line_cov (string trim --right --chars % $ns[2])
            echo $i:$func_cov:$line_cov >> $TEMP
        else
            # no valid data in all.report
            echo $i:0:0 >> $TEMP
        end
    else
        # no all.report at all
        echo $i:-1:-1 >> $TEMP
    end
    
    popd
end


python3 (status dirname)/gen_coverage_report.py --path $TEMP
