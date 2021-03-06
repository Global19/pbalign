#!/usr/bin/env python
###############################################################################
# Copyright (c) 2011-2013, Pacific Biosciences of California, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of Pacific Biosciences nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE.  THIS SOFTWARE IS PROVIDED BY PACIFIC BIOSCIENCES AND ITS
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL PACIFIC BIOSCIENCES OR
# ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

"""This script defines class BowtieSerive, which uses bowtie to align reads."""

# Author: Yuan Li

from __future__ import absolute_import
from pbalign.alignservice.fastabasedalign import FastaBasedAlignService
from os import path
from pbcore.util.Process import backticks
import logging


def bt2BaseName(tempDir, refFile):
    """Return basename of bowtie2 index files.

        Input:
            tempDir: a temporary directory for saving bowtie2
                     index files.
            refFile: the reference sequence file.
        Output:
            string, the basename of bowtie2 index files.

    """
    return path.join(tempDir, path.splitext(path.basename(refFile))[0])


def bt2IndexFiles(baseName):
    """Return a tuple of bowtie2 index files.

        Input:
            baseName: the base name of bowtie2 index files.
        Output:
            list of strings, bowtie2 index files.

    """
    exts = ['1.bt2', '2.bt2', '3.bt2', '4.bt2',
            'rev.1.bt2', 'rev.2.bt2']
    return [".".join([baseName, ext]) for ext in exts]


class BowtieService(FastaBasedAlignService):
    """BowtieService calls bowtie to align reads."""
    @property
    def name(self):
        """Name of the service."""
        return "BowtieService"

    @property
    def progName(self):
        """Program name."""
        return "bowtie2"

    @property
    def scoreSign(self):
        """Score sign for bowtie2 is 1, the larger the better."""
        return 1

    def _resolveAlgorithmOptions(self, options, fileNames):
        """Resolve options specified within --algorithmOptions with
        options parsed from the command-line or the config file, and
        return updated options.

            Input:
                options  : the original pbalign options from argumentList
                           and configFile.
                fileNames: an PBAlignFiles object
            Output:
                new options built by resolving options specified within
                --algorithmOptions and the original pbalign options

        """
        if options.algorithmOptions is None:
            return options

        ignoredBinaryOptions = ['-x', '-S',            # Needs to be computed.
                                '-1', '-2', '-U',      # No paired-end input.
                                '-r', '-q', '--qseq',  # Only accepts FASTA.
                                '--seed']
        ignoredUnitaryOptions = ['--version', '--help']

        items = options.algorithmOptions.split(' ')
        i = 0
        try:
            while i < len(items):
                infoMsg, errMsg, item = "", "", items[i]
                if item == "-k":
                    val = int(items[i+1])
                    if options.maxHits is not None and \
                            int(options.maxHits) != val:
                        errMsg = "bowtie2 -k specified within " + \
                                 "--algorithmOptions is equivalent to " + \
                                 "--maxHits. Conflicting values of " + \
                                 "--algorithmOptions '-k' and " +\
                                 "--maxHits have been found."
                elif item == "-L":
                    val = int(items[i+1])
                    if options.minAnchorSize is not None and \
                            int(options.minAnchorSize) != val:
                        errMsg = "bowtie2 -L specified within " + \
                                 "--algorithmOptions is equivalent to " + \
                                 "--minAnchorSize. Conflicting values " + \
                                 "of --algorithmOptions '-L' and " + \
                                 "--minAnchorSize have been found."
                elif item == "-p":
                    val = int(items[i+1])
                    # The number of threads is not critical.
                    if options.nproc is None or \
                            int(options.npoc) != val:
                        infoMsg = "Over write nproc with {n}.".format(n=val)
                        options.nproc = val
                elif item in ignoredBinaryOptions:
                    pass
                elif item in ignoredUnitaryOptions:
                    del items[i:i+1]
                    continue
                else:
                    i += 1
                    continue

                if errMsg != "":
                    logging.error(errMsg)
                    raise ValueError(errMsg)

                if infoMsg != "":
                    logging.info(self.name + ": Resolve algorithmOptions. " +
                                 infoMsg)

                del items[i:i+2]
        except Exception as e:
            errMsg = "An error occured during parsing algorithmOptions '{ao}'"\
                     .format(ao=options.algorithmOptions) + str(e)
            logging.error(errMsg)
            raise ValueError(errMsg)

        # Update algorithmOptions when resolve is done
        options.algorithmOptions = " ".join(items)

        return options

    def _bt2BuildIndex(self, tempDir, referenceFile):
        """Build bt2 index files.

            Input:
                tempDir      : a temporary directory for saving bowtie2
                               index files.
                referenceFile: the reference sequence file.
            Output:
                list of strings, bowtie2 index files.

        """
        refBaseName = bt2BaseName(tempDir, referenceFile)
        cmdStr = "bowtie2-build -q -f {0} {1}".\
            format(referenceFile, refBaseName)

        logging.info(self.name + ": Build bowtie2 index files.")
        logging.debug(self.name + ": Call {0}".format(cmdStr))

        _output, errCode, errMsg = backticks(cmdStr)
        if (errCode != 0):
            logging.error(self.name + ": Failed to build bowtie2 " +
                          "index files.\n" + errMsg)
            raise RuntimeError(errMsg)

        return bt2IndexFiles(refBaseName)

    def _preProcess(self, inputFileName, referenceFile, regionTable,
                    noSplitSubreads, tempFileManager, isWithinRepository):
        """Preprocess inputs and pre-build reference index files for bowtie2.

        For bowtie2, we need to
        (1) index the reference sequences,
        (2) convert the input PULSE/BASE/FOFN file to FASTA.
            Input:
                inputFilieName : a PacBio BASE/PULSE/FOFN file.
                referenceFile  : a FASTA reference file.
                regionTable    : a region table RGN.H5/FOFN file.
                noSplitSubreads: whether to split subreads or not.
                tempFileManager: temporary file manager.
                isWithinRepository: whether or not the reference is within
                    a reference repository.
            Output:
                String, a FASTA file which can be used by bowtie2.

        """
        # Build bt2 index files and return files that have been built.
        indexFiles = self._bt2BuildIndex(tempFileManager.defaultRootDir,
                                         referenceFile)

        # Register bt2 index files in the temporary file manager.
        for indexFile in indexFiles:
            tempFileManager.RegisterExistingTmpFile(indexFile, own=True)

        # Return a FASTA file that can be used by bowtie2 directly.
        return self._pls2fasta(inputFileName, regionTable, noSplitSubreads)

    def _toCmd(self, options, fileNames, tempFileManager):
        """Return a bowtie2 command line to run in bash.

        Generate a bowtie2 command line based on options and PBAlignFiles.
            Input:
                options  : arguments parsed from the command-line, the
                           config file and --algorithmOptions.
                fileNames: an PBAlignFiles object.
                tempFileManager: temporary file manager.
        Output:
                a command-line string which can be used in bash.

        """
        cmdStr = "bowtie2 "

        if options.maxHits is not None and options.maxHits != "":
            cmdStr += " -k {maxHits}".format(maxHits=options.maxHits)

        if options.nproc is not None and options.nproc != "":
            cmdStr += " -p {nproc}".format(nproc=options.nproc)

        if options.algorithmOptions is not None:
            cmdStr += " {opts} ".format(opts=options.algorithmOptions)

        if options.seed is not None and options.seed != "":
            cmdStr += " --seed {seed} ".format(seed=options.seed)

        refBaseName = bt2BaseName(tempFileManager.defaultRootDir,
                                  fileNames.targetFileName)
        cmdStr += "-x {refBase} -f {queryFile} -S {outFile} ".\
            format(refBase=refBaseName,
                   queryFile=fileNames.queryFileName,
                   outFile=fileNames.alignerSamOut)

        return cmdStr

    def _postProcess(self):
        """Postprocess after alignment is done."""
        logging.debug("Preprocess after alignment is done. ")
