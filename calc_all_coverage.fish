#!/usr/bin/env fish

####################################################
#
#
# Merge and calculate all coverage data.
#
# Author: Mao Yifu, maoif@ios.ac.cn
#
#
####################################################

# TODO check whether we have be in the src path to use llvm-cov
# It seems ok in coverage/

function notice
    echo '[coverage] ' $argv
end


cd $TREC_PERF_DIR

ls *.profraw > /dev/null
if test $status -ne 0
    ls
    notice 'raw profile data not found, exiting'
    exit -1
end

ls *.refinement > /dev/null
if test $status -ne 0
    ls
    notice 'refinement file not found, exiting'
    exit -1
end

notice 'Merging profile data...'

# read refinement file to get the exes
set rs (ls *.refinement)
cat $rs[1] | while read -l i
    # .perf-bin: align with test-wrapper
    set true_exe (echo $i | cut -d' ' -f2).perf-bin

    # If `true_exe` is a symlink, it's a link to wrap script... 
    # See test-wrapper.py for more info.
    file $true_exe | grep --quiet 'symbolic link'
    if test $status -eq 0
        set target (dirname $true_exe)/(readlink $true_exe).perf-bin
        if test -e $target
            set true_exe $target
        else
            notice symlink $true_exe with $target does not exist
        end
    end

    set exes $exes $true_exe
    set objexes $objexes -object $true_exe
    # debug
    file $true_exe
    ldd  $true_exe
    objdump -h $true_exe

    echo
end

# merge all prof data into one
llvm-profdata merge -sparse *.profraw -o all.profdata

# read all .sos file, if any
ls *.sos > /dev/null
if test $status -eq 0
    set objs (cat *.sos | sort | uniq)
    # debug
    for i in $objs
        objdump -h $i
        # need `-object` to make the report complete
        set objobjs $objobjs -object $i
    end
end

notice exes: $objexes
notice objs: $objobjs

cd -

llvm-cov report -instr-profile $TREC_PERF_DIR/all.profdata $objexes $objobjs &> $TREC_PERF_DIR/all.report
llvm-cov show   -instr-profile $TREC_PERF_DIR/all.profdata -format=html -output-dir=$TREC_PERF_DIR/all_report $objexes $objobjs &> $TREC_PERF_DIR/all_cov.log