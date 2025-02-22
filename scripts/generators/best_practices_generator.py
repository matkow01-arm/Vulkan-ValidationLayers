#!/usr/bin/python3 -i
#
# Copyright (c) 2015-2023 The Khronos Group Inc.
# Copyright (c) 2015-2023 Valve Corporation
# Copyright (c) 2015-2023 LunarG, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys,os
from common_codegen import *
from generators.generator_utils import *
from generators.base_generator import BaseGenerator
from typing import List

# We want to take the following C Prototype:
#
# VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(
#     const VkInstanceCreateInfo*                 pCreateInfo,
#     const VkAllocationCallbacks*                pAllocator,
#     VkInstance*                                 pInstance);
#
# ... and apply name change, remove macros, add result parameter to the end so it looks like:
#
# void PostCallRecordCreateInstance(
#     const VkInstanceCreateInfo*                 pCreateInfo,
#     const VkAllocationCallbacks*                pAllocator,
#     VkInstance*                                 pInstance,
#     VkResult                                    result);
#
def createPostCallRecordPrototype(prototype: str, className: str = "",
                                    override: bool = False,
                                    extraParam: bool = False) -> str:
    prototype = prototype.split("VKAPI_CALL ")[1]
    prototype = f'void {className}PostCallRecord{prototype[2:]}'
    prototype = prototype.replace(');', ',\n    VkResult                                    result) {\n')
    if override:
        prototype = prototype.replace(') {', ') override;')
    if extraParam:
        prototype = prototype.replace(')', ',\n    void*                                       state_data)')
    return prototype

# If there is another success code other than VK_SUCCESS
def hasNonVkSuccess(successCodes: List[str]) -> bool:
    if successCodes is None or len(successCodes) == 0:
        return False
    return len(successCodes) > 1 or 'VK_SUCCESS' not in successCodes

class BestPracticesOutputGenerator(BaseGenerator):
    def __init__(self,
                 errFile = sys.stderr,
                 warnFile = sys.stderr,
                 diagFile = sys.stdout):
        BaseGenerator.__init__(self, errFile, warnFile, diagFile)
        self.headerFile = False # Header file generation flag
        self.sourceFile = False # Source file generation flag

        # Commands which are not autogenerated but still intercepted
        # More are added from a first pass over the functions
        self.no_autogen_list = [
            'vkEnumerateInstanceVersion',
            'vkCreateValidationCacheEXT',
            'vkDestroyValidationCacheEXT',
            'vkMergeValidationCachesEXT',
            'vkGetValidationCacheDataEXT',
        ]

        # TODO - Is this a common list across files?
        # Commands that require an extra parameter for state sharing between validate/record steps
        self.extra_parameter_list = [
            "vkCreateShaderModule",
            "vkCreateGraphicsPipelines",
            "vkCreateComputePipelines",
            "vkAllocateDescriptorSets",
            "vkCreateRayTracingPipelinesNV",
            "vkCreateRayTracingPipelinesKHR",
        ]
        # Commands that have a manually written post-call-record step which needs to be called from the autogen'd fcn
        self.manual_postcallrecord_list = [
            'vkAllocateDescriptorSets',
            'vkQueuePresentKHR',
            'vkQueueBindSparse',
            'vkCreateGraphicsPipelines',
            'vkGetPhysicalDeviceSurfaceCapabilitiesKHR',
            'vkGetPhysicalDeviceSurfaceCapabilities2KHR',
            'vkGetPhysicalDeviceSurfaceCapabilities2EXT',
            'vkGetPhysicalDeviceSurfacePresentModesKHR',
            'vkGetPhysicalDeviceSurfaceFormatsKHR',
            'vkGetPhysicalDeviceSurfaceFormats2KHR',
            'vkGetPhysicalDeviceDisplayPlanePropertiesKHR',
            'vkGetSwapchainImagesKHR',
            # AMD tracked
            'vkCreateComputePipelines',
            'vkCmdPipelineBarrier',
            'vkQueueSubmit',
        ]

        self.extension_info = dict()

    def generate(self):
        self.headerFile = (self.filename == 'best_practices.h')
        self.sourceFile = (self.filename == 'best_practices.cpp')

        copyright = f'''{fileIsGeneratedWarning(os.path.basename(__file__))}
/***************************************************************************
*
* Copyright (c) 2015-2023 The Khronos Group Inc.
* Copyright (c) 2015-2023 Valve Corporation
* Copyright (c) 2015-2023 LunarG, Inc.
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
****************************************************************************/\n'''
        self.write(copyright)
        self.write('// NOLINTBEGIN') # Wrap for clang-tidy to ignore

        # Build additional pass of functions to ignore
        for name, command in self.vk.commands.items():
            if command.returnType != 'VkResult':
                self.no_autogen_list.append(name)
            # This is just to remove un-used commands from be generated
            # This can be removed if another use for these commands are needed
            if (command.errorCodes is None and not hasNonVkSuccess(command.successCodes)):
                self.no_autogen_list.append(name)

        if self.headerFile:
            self.generateHeader()
        else:
            self.generateSource()

        self.write('// NOLINTEND') # Wrap for clang-tidy to ignore

    def generateHeader(self):
        self.write('#pragma once')
        self.write('#include <vulkan/vulkan_core.h>')
        self.write('#include "containers/custom_containers.h"')
        # List all Function declarations
        for name, command in self.vk.commands.items():
            if name in self.no_autogen_list:
                continue

            out = []
            out.append(getProtectMacro(command, ifdef=True))
            out.append(createPostCallRecordPrototype(command.cPrototype,
                                                     extraParam=(name in self.extra_parameter_list),
                                                     override=True))
            out.append('\n')
            out.append(getProtectMacro(command, endif=True))
            self.write("".join(out))

        # Create deprecated extension map
        out = []
        out.append('const vvl::unordered_map<std::string, DeprecationData>  deprecated_extensions = {\n')
        for name, info in self.vk.extensions.items():
            target = None
            reason = None
            if info.promotedTo is not None:
                reason = 'kExtPromoted'
                target = info.promotedTo
            elif info.obsoletedBy is not None:
                reason = 'kExtObsoleted'
                target = info.obsoletedBy
            elif info.deprecatedBy is not None:
                reason = 'kExtDeprecated'
                target = info.deprecatedBy
            else:
                continue
            out.append(f'    {{"{name}", {{{reason}, "{target}"}}}},\n')
        out.append('};\n')
        self.write("".join(out))

        out = []
        out.append('const vvl::unordered_map<std::string, std::string> special_use_extensions = {\n')
        for name, info in self.vk.extensions.items():
            if info.specialUse is not None:
                out.append('    {{"{}", "{}"}},\n'.format(name, ', '.join(info.specialUse)))
        out.append('};\n')
        self.write("".join(out))

    def generateSource(self):
        self.write('#include "chassis.h"')
        self.write('#include "best_practices/best_practices_validation.h"')
        for name, command in self.vk.commands.items():
            if name in self.no_autogen_list:
                continue

            paramList = [param.name for param in command.params]
            paramList.append('result')
            if name in self.extra_parameter_list:
                paramList.append('state_data')
            params = ', '.join(paramList)

            out = []
            out.append(getProtectMacro(command, ifdef=True))
            out.append(createPostCallRecordPrototype(command.cPrototype,
                                                     extraParam=(name in self.extra_parameter_list),
                                                     className='BestPractices::'))
            out.append(f'    ValidationStateTracker::PostCallRecord{name[2:]}({params});\n')
            if name in self.manual_postcallrecord_list:
                out.append('    ManualPostCallRecord{}({});\n'.format(name[2:], params))

            if hasNonVkSuccess(command.successCodes):
                out.append('    if (result > VK_SUCCESS) {\n')
                results = [ x for x in command.successCodes if x != 'VK_SUCCESS' ]
                out.append('        LogPositiveSuccessCode("{}", result); // {}\n'.format(name, ', '.join(results)))
                out.append('        return;\n')
                out.append('    }\n')

            if command.errorCodes is not None:
                out.append('    if (result < VK_SUCCESS) {\n')
                out.append('        LogErrorCode("{}", result); // {}\n'.format(name, ', '.join(command.errorCodes)))
                out.append('    }\n')

            out.append('}\n')
            out.append(getProtectMacro(command, endif=True))
            self.write(''.join(out))
