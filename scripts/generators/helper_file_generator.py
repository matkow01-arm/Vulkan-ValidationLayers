#!/usr/bin/python3 -i
#
# Copyright (c) 2015-2023 The Khronos Group Inc.
# Copyright (c) 2015-2023 Valve Corporation
# Copyright (c) 2015-2023 LunarG, Inc.
# Copyright (c) 2015-2023 Google Inc.
# Copyright (c) 2023-2023 RasterGrid Kft.
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

import re,sys,os
import xml.etree.ElementTree as etree
from generator import *
from collections import namedtuple
from common_codegen import *

#
# HelperFileOutputGenerator - subclass of OutputGenerator. Outputs Vulkan helper files
class HelperFileOutputGenerator(OutputGenerator):
    """Generate helper file based on XML element attributes"""
    def __init__(self,
                 errFile = sys.stderr,
                 warnFile = sys.stderr,
                 diagFile = sys.stdout):
        OutputGenerator.__init__(self, errFile, warnFile, diagFile)
        # Internal state - accumulators for different inner block text
        self.enum_output = ''                             # string built up of enum string routines
        # Internal state - accumulators for different inner block text
        self.structNames = []                             # List of Vulkan struct typenames
        self.structTypes = dict()                         # Map of Vulkan struct typename to required VkStructureType
        self.structMembers = []                           # List of StructMemberData records for all Vulkan structs
        self.core_object_types = []                       # Handy copy of core_object_type enum data
        self.device_extension_info = dict()               # Dict of device extension name defines and ifdef values
        self.instance_extension_info = dict()             # Dict of instance extension name defines and ifdef values
        self.structextends_list = []                      # List of structs which extend another struct via pNext
        self.structOrUnion = dict()                       # Map of Vulkan typename to 'struct' or 'union'

        # Named tuples to store struct and command data
        self.StructType = namedtuple('StructType', ['name', 'value'])
        self.CommandParam = namedtuple('CommandParam', ['type', 'name', 'ispointer', 'isstaticarray', 'isconst', 'iscount', 'len', 'extstructs', 'cdecl'])
        self.StructMemberData = namedtuple('StructMemberData', ['name', 'members', 'ifdef_protect', 'allowduplicate'])

        self.custom_construct_params = {
            # safe_VkGraphicsPipelineCreateInfo needs to know if subpass has color and\or depth\stencil attachments to use its pointers
            'VkGraphicsPipelineCreateInfo' :
                ', const bool uses_color_attachment, const bool uses_depthstencil_attachment',
            # safe_VkPipelineViewportStateCreateInfo needs to know if viewport and scissor is dynamic to use its pointers
            'VkPipelineViewportStateCreateInfo' :
                ', const bool is_dynamic_viewports, const bool is_dynamic_scissors',
            # safe_VkAccelerationStructureBuildGeometryInfoKHR needs to know if we're doing a host or device build
            'VkAccelerationStructureBuildGeometryInfoKHR' :
                ', const bool is_host, const VkAccelerationStructureBuildRangeInfoKHR *build_range_infos',
            # safe_VkAccelerationStructureGeometryKHR needs to know if we're doing a host or device build
            'VkAccelerationStructureGeometryKHR' :
                ', const bool is_host, const VkAccelerationStructureBuildRangeInfoKHR *build_range_info',
            # safe_VkDescriptorDataEXT needs to know what field of union is intialized
            'VkDescriptorDataEXT' :
                ', const VkDescriptorType type',
            'VkPipelineRenderingCreateInfo' : ''
        }

    vk_api_version_definition = """
#define VVL_UNRECOGNIZED_API_VERSION 0xFFFFFFFF

class APIVersion {
  public:
    APIVersion() : api_version_(VVL_UNRECOGNIZED_API_VERSION) {}

    APIVersion(uint32_t api_version) : api_version_(api_version) {}

    APIVersion& operator=(uint32_t api_version) {
        api_version_ = api_version;
        return *this;
    }

    bool valid() const { return api_version_ != VVL_UNRECOGNIZED_API_VERSION; }
    uint32_t value() const { return api_version_; }
    uint32_t major() const { return VK_API_VERSION_MAJOR(api_version_); }
    uint32_t minor() const { return VK_API_VERSION_MINOR(api_version_); }
    uint32_t patch() const { return VK_API_VERSION_PATCH(api_version_); }

    bool operator<(APIVersion api_version) const { return api_version_ < api_version.api_version_; }
    bool operator<=(APIVersion api_version) const { return api_version_ <= api_version.api_version_; }
    bool operator>(APIVersion api_version) const { return api_version_ > api_version.api_version_; }
    bool operator>=(APIVersion api_version) const { return api_version_ >= api_version.api_version_; }
    bool operator==(APIVersion api_version) const { return api_version_ == api_version.api_version_; }
    bool operator!=(APIVersion api_version) const { return api_version_ != api_version.api_version_; }

  private:
    uint32_t api_version_;
};

static inline APIVersion NormalizeApiVersion(APIVersion specified_version) {
    if (specified_version < VK_API_VERSION_1_1)
        return VK_API_VERSION_1_0;
    else if (specified_version < VK_API_VERSION_1_2)
        return VK_API_VERSION_1_1;
    else if (specified_version < VK_API_VERSION_1_3)
        return VK_API_VERSION_1_2;
    else
        return VK_API_VERSION_1_3;
}
"""

    #
    # Generate APIVersion definition
    def genAPIVersionDefinition(self):
        return self.vk_api_version_definition

    #
    # Called once at the beginning of each run
    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)
        # Initialize members that require the tree
        self.handle_types = GetHandleTypes(self.registry.tree)
        # User-supplied prefix text, if any (list of strings)
        self.helper_file_type = genOpts.helper_file_type
        # File Comment
        file_comment = '// *** THIS FILE IS GENERATED - DO NOT EDIT ***\n'
        file_comment += '// See {} for modifications\n'.format(os.path.basename(__file__))
        write(file_comment, file=self.outFile)
        # Copyright Notice
        copyright = ''
        copyright += '\n'
        copyright += '/***************************************************************************\n'
        copyright += ' *\n'
        copyright += ' * Copyright (c) 2015-2023 The Khronos Group Inc.\n'
        copyright += ' * Copyright (c) 2015-2023 Valve Corporation\n'
        copyright += ' * Copyright (c) 2015-2023 LunarG, Inc.\n'
        copyright += ' * Copyright (c) 2015-2023 Google Inc.\n'
        copyright += ' *\n'
        copyright += ' * Licensed under the Apache License, Version 2.0 (the "License");\n'
        copyright += ' * you may not use this file except in compliance with the License.\n'
        copyright += ' * You may obtain a copy of the License at\n'
        copyright += ' *\n'
        copyright += ' *     http://www.apache.org/licenses/LICENSE-2.0\n'
        copyright += ' *\n'
        copyright += ' * Unless required by applicable law or agreed to in writing, software\n'
        copyright += ' * distributed under the License is distributed on an "AS IS" BASIS,\n'
        copyright += ' * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n'
        copyright += ' * See the License for the specific language governing permissions and\n'
        copyright += ' * limitations under the License.\n'
        copyright += ' ****************************************************************************/\n'
        write(copyright, file=self.outFile)
    #
    # Write generated file content to output file
    def endFile(self):
        dest_file = ''
        dest_file += self.OutputDestFile()
        # Remove blank lines at EOF
        if dest_file.endswith('\n'):
            dest_file = dest_file[:-1]
        write(dest_file, file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFile(self)
    #
    # Override parent class to be notified of the beginning of an extension
    def beginFeature(self, interface, emit):
        # Start processing in superclass
        OutputGenerator.beginFeature(self, interface, emit)
        self.featureExtraProtect = GetFeatureProtect(interface)

        if interface.tag != 'extension':
            return
        name = self.featureName
        index = 0
        while interface[0][index].tag == 'comment':
            index += 1
        nameElem = interface[0][index + 1]
        name_define = nameElem.get('name')
        if 'EXTENSION_NAME' not in name_define:
            print("Error in vk.xml file -- extension name is not available")
        requires = interface.get('depends')
        if requires is not None:
            # This is a work around for https://github.com/KhronosGroup/Vulkan-ValidationLayers/issues/5372
            requires = re.sub(r',VK_VERSION_1_\d+', '', requires)
            required_extensions = exprValues(parseExpr(requires))
        else:
            required_extensions = list()
        info = { 'define': GetNameDefine(interface), 'ifdef':self.featureExtraProtect, 'reqs':required_extensions }
        if interface.get('type') == 'instance':
            self.instance_extension_info[name] = info
        else:
            self.device_extension_info[name] = info

    #
    # Override parent class to be notified of the end of an extension
    def endFeature(self):
        # Finish processing in superclass
        OutputGenerator.endFeature(self)
    #
    # Grab group (e.g. C "enum" type) info to output for enum-string conversion helper
    def genGroup(self, groupinfo, groupName, alias):
        OutputGenerator.genGroup(self, groupinfo, groupName, alias)

    #
    # Called for each type -- if the type is a struct/union, grab the metadata
    def genType(self, typeinfo, name, alias):
        OutputGenerator.genType(self, typeinfo, name, alias)
        typeElem = typeinfo.elem
        # If the type is a struct type, traverse the imbedded <member> tags generating a structure.
        # Otherwise, emit the tag text.
        category = typeElem.get('category')

        if (category == 'struct' or category == 'union'):
            self.structNames.append(name)
            self.genStruct(typeinfo, name, alias)
            if (category == 'union'):
                self.structOrUnion[name] = 'union'
            else:
                self.structOrUnion[name] = 'struct'

    #
    # Check if the parameter passed in is a pointer
    def paramIsPointer(self, param):
        ispointer = False
        for elem in param:
            if elem.tag == 'type' and elem.tail is not None and '*' in elem.tail:
                ispointer = True
        return ispointer
    #
    # Check if the parameter passed in is a static array
    def paramIsStaticArray(self, param):
        isstaticarray = 0
        paramname = param.find('name')
        if (paramname.tail is not None) and ('[' in paramname.tail):
            isstaticarray = paramname.tail.count('[')
        return isstaticarray
    #
    # Retrieve the type and name for a parameter
    def getTypeNameTuple(self, param):
        type = ''
        name = ''
        for elem in param:
            if elem.tag == 'type':
                type = noneStr(elem.text)
            elif elem.tag == 'name':
                name = noneStr(elem.text)
        return (type, name)
    #
    # Retrieve the value of the len tag
    def getLen(self, param):
        result = None
        len = param.attrib.get('len')
        if len and len != 'null-terminated':
            # For string arrays, 'len' can look like 'count,null-terminated', indicating that we
            # have a null terminated array of strings.  We strip the null-terminated from the
            # 'len' field and only return the parameter specifying the string count
            if 'null-terminated' in len:
                result = len.split(',')[0]
            else:
                result = len
            if 'altlen' in param.attrib:
                # Elements with latexmath 'len' also contain a C equivalent 'altlen' attribute
                # Use indexing operator instead of get() so we fail if the attribute is missing
                result = param.attrib['altlen']
            # Spec has now notation for len attributes, using :: instead of platform specific pointer symbol
            result = str(result).replace('::', '->')
        return result
    #
    # Check if a structure is or contains a dispatchable (dispatchable = True) or
    # non-dispatchable (dispatchable = False) handle
    def TypeContainsObjectHandle(self, handle_type, dispatchable):
        if dispatchable:
            type_check = self.handle_types.IsDispatchable
        else:
            type_check = self.handle_types.IsNonDispatchable
        if type_check(handle_type):
            return True
        # if handle_type is a struct, search its members
        if handle_type in self.structNames:
            member_index = next((i for i, v in enumerate(self.structMembers) if v[0] == handle_type), None)
            if member_index is not None:
                for item in self.structMembers[member_index].members:
                    if type_check(item.type):
                        return True
        return False
    #
    # Generate local ready-access data describing Vulkan structures and unions from the XML metadata
    def genStruct(self, typeinfo, typeName, alias):
        OutputGenerator.genStruct(self, typeinfo, typeName, alias)
        members = typeinfo.elem.findall('.//member')
        # Iterate over members once to get length parameters for arrays
        lens = set()
        for member in members:
            len = self.getLen(member)
            if len:
                lens.add(len)
        # Generate member info
        membersInfo = []
        for member in members:
            # Get the member's type and name
            info = self.getTypeNameTuple(member)
            type = info[0]
            name = info[1]
            cdecl = self.makeCParamDecl(member, 1)
            # Process VkStructureType
            if type == 'VkStructureType':
                # Extract the required struct type value from the comments
                # embedded in the original text defining the 'typeinfo' element
                rawXml = etree.tostring(typeinfo.elem).decode('ascii')
                result = re.search(r'VK_STRUCTURE_TYPE_\w+', rawXml)
                if result:
                    value = result.group(0)
                    # Store the required type value
                    self.structTypes[typeName] = self.StructType(name=name, value=value)
            # Store pointer/array/string info
            isstaticarray = self.paramIsStaticArray(member)
            membersInfo.append(self.CommandParam(type=type,
                                                 name=name,
                                                 ispointer=self.paramIsPointer(member),
                                                 isstaticarray=isstaticarray,
                                                 isconst=True if 'const' in cdecl else False,
                                                 iscount=True if name in lens else False,
                                                 len=self.getLen(member),
                                                 extstructs=self.registry.validextensionstructs[typeName] if name == 'pNext' else None,
                                                 cdecl=cdecl))
        # If true, this structure type can appear multiple times within a pNext chain
        allowduplicate = self.getBoolAttribute(typeinfo.elem, 'allowduplicate')
        # If this struct extends another, keep its name in list for further processing
        if typeinfo.elem.attrib.get('structextends') is not None:
            self.structextends_list.append(typeName)
        self.structMembers.append(self.StructMemberData(name=typeName, members=membersInfo, ifdef_protect=self.featureExtraProtect, allowduplicate=allowduplicate))

    #
    # Helper function for declaring a counter variable only once
    def DeclareCounter(self, string_var, declare_flag):
        if declare_flag == False:
            string_var += '        uint32_t i = 0;\n'
            declare_flag = True
        return string_var, declare_flag

    #
    # Generate extension helper header file
    def GenerateExtensionHelperHeader(self):

        promoted_1_1_exts = self.registry.tree.findall('*/extension[@promotedto="VK_VERSION_1_1"]')
        V_1_0_instance_extensions_promoted_to_V_1_1_core = sorted([e.get('name') for e in promoted_1_1_exts if e.get('type') == 'instance'])
        V_1_0_device_extensions_promoted_to_V_1_1_core = sorted([e.get('name') for e in promoted_1_1_exts if e.get('type') == 'device'])

        promoted_1_2_exts = self.registry.tree.findall('*/extension[@promotedto="VK_VERSION_1_2"]')
        V_1_1_instance_extensions_promoted_to_V_1_2_core = sorted([e.get('name') for e in promoted_1_2_exts if e.get('type') == 'instance'])
        V_1_1_device_extensions_promoted_to_V_1_2_core = sorted([e.get('name') for e in promoted_1_2_exts if e.get('type') == 'device'])

        promoted_1_3_exts = self.registry.tree.findall('*/extension[@promotedto="VK_VERSION_1_3"]')
        V_1_2_instance_extensions_promoted_to_V_1_3_core = sorted([e.get('name') for e in promoted_1_3_exts if e.get('type') == 'instance'])
        V_1_2_device_extensions_promoted_to_V_1_3_core = sorted([e.get('name') for e in promoted_1_3_exts if e.get('type') == 'device'])

        output = ['''#pragma once

#include <string>
#include <utility>
#include <set>
#include <array>
#include <vector>
#include <cassert>

#include <vulkan/vulkan.h>
#include "containers/custom_containers.h"
#define VK_VERSION_1_1_NAME "VK_VERSION_1_1"

enum ExtEnabled : unsigned char {
    kNotEnabled,
    kEnabledByCreateinfo,
    kEnabledByApiLevel,
    kEnabledByInteraction,
};

/*
This function is a helper to know if the extension is enabled.

Times to use it
- To determine the VUID
- The VU mentions the use of the extension
- Extension exposes property limits being validated
- Checking not enabled
    - if (!IsExtEnabled(...)) { }
- Special extensions that being EXPOSED alters the VUs
    - IsExtEnabled(device_extensions.vk_khr_portability_subset)
- Special extensions that alter behaviour of enabled
    - IsExtEnabled(device_extensions.vk_khr_maintenance*)

Times to NOT use it
    - If checking if a struct or enum is being used. There are a stateless checks
      to make sure the new Structs/Enums are not being used without this enabled.
    - If checking if the extension's feature enable status, because if the feature
      is enabled, then we already validated that extension is enabled.
    - Some variables (ex. viewMask) require the extension to be used if non-zero
*/
[[maybe_unused]] static bool IsExtEnabled(ExtEnabled extension) {
    return (extension != kNotEnabled);
};

[[maybe_unused]] static bool IsExtEnabledByCreateinfo(ExtEnabled extension) {
    return (extension == kEnabledByCreateinfo);
};
#define VK_VERSION_1_2_NAME "VK_VERSION_1_2"
#define VK_VERSION_1_3_NAME "VK_VERSION_1_3"''']

        output.append(self.genAPIVersionDefinition())

        for type in ['Instance', 'Device']:
            struct_type = '%sExtensions' % type
            if type == 'Instance':
                extension_dict = self.instance_extension_info
                promoted_1_1_ext_list = V_1_0_instance_extensions_promoted_to_V_1_1_core
                promoted_1_2_ext_list = V_1_1_instance_extensions_promoted_to_V_1_2_core
                promoted_1_3_ext_list = V_1_2_instance_extensions_promoted_to_V_1_3_core
                struct_decl = 'struct %s {' % struct_type
                instance_struct_type = struct_type
            else:
                extension_dict = self.device_extension_info
                promoted_1_1_ext_list = V_1_0_device_extensions_promoted_to_V_1_1_core
                promoted_1_2_ext_list = V_1_1_device_extensions_promoted_to_V_1_2_core
                promoted_1_3_ext_list = V_1_2_device_extensions_promoted_to_V_1_3_core
                struct_decl = 'struct %s : public %s {' % (struct_type, instance_struct_type)

            extension_items = sorted(extension_dict.items())

            field_name = { ext_name: ext_name.lower() for ext_name, info in extension_items }

            # Add in pseudo-extensions for core API versions so real extensions can depend on them
            extension_dict['VK_VERSION_1_3'] = {'define':"VK_VERSION_1_3_NAME", 'ifdef':None, 'reqs':[]}
            field_name['VK_VERSION_1_3'] = "vk_feature_version_1_3"
            extension_dict['VK_VERSION_1_2'] = {'define':"VK_VERSION_1_2_NAME", 'ifdef':None, 'reqs':[]}
            field_name['VK_VERSION_1_2'] = "vk_feature_version_1_2"
            extension_dict['VK_VERSION_1_1'] = {'define':"VK_VERSION_1_1_NAME", 'ifdef':None, 'reqs':[]}
            field_name['VK_VERSION_1_1'] = "vk_feature_version_1_1"

            if type == 'Instance':
                instance_field_name = field_name
                instance_extension_dict = extension_dict
            else:
                # Get complete field name and extension data for both Instance and Device extensions
                field_name.update(instance_field_name)
                extension_dict = extension_dict.copy()  # Don't modify the self.<dict> we're pointing to
                extension_dict.update(instance_extension_dict)

            # Output the data member list
            struct  = [struct_decl]
            struct.extend([ '    ExtEnabled vk_feature_version_1_1{kNotEnabled};'])
            struct.extend([ '    ExtEnabled vk_feature_version_1_2{kNotEnabled};'])
            struct.extend([ '    ExtEnabled vk_feature_version_1_3{kNotEnabled};'])
            struct.extend([ '    ExtEnabled %s{kNotEnabled};' % field_name[ext_name] for ext_name, info in extension_items])
            # TODO Issue 4841 -  It looks like framework is not ready for two properties structs per extension (like VK_EXT_descriptor_buffer have). Workarounding.
            struct.extend([ '    ExtEnabled vk_ext_descriptor_buffer_density{kNotEnabled};'])

            # Construct the extension information map -- mapping name to data member (field), and required extensions
            # The map is contained within a static function member for portability reasons.
            info_type = '%sInfo' % type
            info_map_type = '%sMap' % info_type
            req_type = '%sReq' % type
            req_vec_type = '%sVec' % req_type
            struct.extend([
                '',
                '    struct %s {' % req_type,
                '        const ExtEnabled %s::* enabled;' % struct_type,
                '        const char *name;',
                '    };',
                '    typedef std::vector<%s> %s;' % (req_type, req_vec_type),
                '    struct %s {' % info_type,
                '       %s(ExtEnabled %s::* state_, const %s requirements_): state(state_), requirements(requirements_) {}' % ( info_type, struct_type, req_vec_type),
                '       ExtEnabled %s::* state;' % struct_type,
                '       %s requirements;' % req_vec_type,
                '    };',
                '',
                '    typedef vvl::unordered_map<std::string,%s> %s;' % (info_type, info_map_type),
                '    static const %s &get_info_map() {' %info_map_type,
                '        static const %s info_map = {' % info_map_type ])
            struct.extend([
                '            {"VK_VERSION_1_1", %sInfo(&%sExtensions::vk_feature_version_1_1, {})},' % (type, type)])
            struct.extend([
                '            {"VK_VERSION_1_2", %sInfo(&%sExtensions::vk_feature_version_1_2, {})},' % (type, type)])
            struct.extend([
                '            {"VK_VERSION_1_3", %sInfo(&%sExtensions::vk_feature_version_1_3, {})},' % (type, type)])

            field_format = '&' + struct_type + '::%s'
            req_format = '{' + field_format+ ', %s}'
            req_indent = '\n                           '
            req_join = ',' + req_indent
            info_format = ('            {%s, ' + info_type + '(' + field_format + ', {%s})},')
            def format_info(ext_name, info):
                reqs = req_join.join([req_format % (field_name[req], extension_dict[req]['define']) for req in info['reqs']])
                return info_format % (info['define'], field_name[ext_name], '{%s}' % (req_indent + reqs) if reqs else '')

            struct.extend([Guarded(info['ifdef'], format_info(ext_name, info)) for ext_name, info in extension_items])
            struct.extend([
                '        };',
                '',
                '        return info_map;',
                '    }',
                '',
                '    static const %s &get_info(const char *name) {' % info_type,
                '        static const %s empty_info {nullptr, %s()};' % (info_type, req_vec_type),
                '        const auto &ext_map = %s::get_info_map();' % struct_type,
                '        const auto info = ext_map.find(name);',
                '        if ( info != ext_map.cend()) {',
                '            return info->second;',
                '        }',
                '        return empty_info;',
                '    }',
                ''])

            if type == 'Instance':
                struct.extend([
                    '',
                    '    APIVersion InitFromInstanceCreateInfo(APIVersion requested_api_version, const VkInstanceCreateInfo *pCreateInfo) {'])
            else:
                struct.extend([
                    '    %s() = default;' % struct_type,
                    '    %s(const %s& instance_ext) : %s(instance_ext) {}' % (struct_type, instance_struct_type, instance_struct_type),
                    '',
                    '    APIVersion InitFromDeviceCreateInfo(const %s *instance_extensions, APIVersion requested_api_version,' % instance_struct_type,
                    '                                        const VkDeviceCreateInfo *pCreateInfo = nullptr) {',
                    '        // Initialize: this to defaults,  base class fields to input.',
                    '        assert(instance_extensions);',
                    '        *this = %s(*instance_extensions);' % struct_type,
                    '']),
            struct.extend([
                '',
                f'        constexpr std::array<const char*, {len(promoted_1_1_ext_list)}> V_1_1_promoted_{type.lower()}_apis = {{' ])
            struct.extend(['            %s,' % extension_dict[ext_name]['define'] for ext_name in promoted_1_1_ext_list])
            struct.extend([
                '        };',
                f'        constexpr std::array<const char*, {len(promoted_1_2_ext_list)}> V_1_2_promoted_{type.lower()}_apis = {{' ])
            struct.extend(['            %s,' % extension_dict[ext_name]['define'] for ext_name in promoted_1_2_ext_list])
            struct.extend([
                '        };',
                f'        constexpr std::array<const char*, {len(promoted_1_3_ext_list)}> V_1_3_promoted_{type.lower()}_apis = {{' ])
            struct.extend(['            %s,' % extension_dict[ext_name]['define'] for ext_name in promoted_1_3_ext_list])
            struct.extend([
                '        };',
                '',
                '        // Initialize struct data, robust to invalid pCreateInfo',
                '        auto api_version = NormalizeApiVersion(requested_api_version);',
                '        if (api_version >= VK_API_VERSION_1_1) {',
                '            auto info = get_info("VK_VERSION_1_1");',
                '            if (info.state) this->*(info.state) = kEnabledByCreateinfo;',
                '            for (auto promoted_ext : V_1_1_promoted_%s_apis) {' % type.lower(),
                '                info = get_info(promoted_ext);',
                '                assert(info.state);',
                '                if (info.state) this->*(info.state) = kEnabledByApiLevel;',
                '            }',
                '        }',
                '        if (api_version >= VK_API_VERSION_1_2) {',
                '            auto info = get_info("VK_VERSION_1_2");',
                '            if (info.state) this->*(info.state) = kEnabledByCreateinfo;',
                '            for (auto promoted_ext : V_1_2_promoted_%s_apis) {' % type.lower(),
                '                info = get_info(promoted_ext);',
                '                assert(info.state);',
                '                if (info.state) this->*(info.state) = kEnabledByApiLevel;',
                '            }',
                '        }',
                '        if (api_version >= VK_API_VERSION_1_3) {',
                '            auto info = get_info("VK_VERSION_1_3");',
                '            if (info.state) this->*(info.state) = kEnabledByCreateinfo;',
                '            for (auto promoted_ext : V_1_3_promoted_%s_apis) {' % type.lower(),
                '                info = get_info(promoted_ext);',
                '                assert(info.state);',
                '                if (info.state) this->*(info.state) = kEnabledByApiLevel;',
                '            }',
                '        }',
                '        // CreateInfo takes precedence over promoted',
                '        if (pCreateInfo && pCreateInfo->ppEnabledExtensionNames) {',
                '            for (uint32_t i = 0; i < pCreateInfo->enabledExtensionCount; i++) {',
                '                if (!pCreateInfo->ppEnabledExtensionNames[i]) continue;',
                '                auto info = get_info(pCreateInfo->ppEnabledExtensionNames[i]);',
                '                if (info.state) this->*(info.state) = kEnabledByCreateinfo;',
                '            }',
                '        }' ])
            if type == 'Device':
                struct.extend([
                    '        // Workaround for functions being introduced by multiple extensions, until the layer is fixed to handle this correctly',
                    '        // See https://github.com/KhronosGroup/Vulkan-ValidationLayers/issues/5579 and https://github.com/KhronosGroup/Vulkan-ValidationLayers/issues/5600',
                    '        {',
                    '            constexpr std::array shader_object_interactions = {',
                    '                VK_EXT_EXTENDED_DYNAMIC_STATE_EXTENSION_NAME,',
                    '                VK_EXT_EXTENDED_DYNAMIC_STATE_2_EXTENSION_NAME,',
                    '                VK_EXT_EXTENDED_DYNAMIC_STATE_3_EXTENSION_NAME,',
                    '                VK_EXT_VERTEX_INPUT_DYNAMIC_STATE_EXTENSION_NAME,',
                    '            };',
                    '            auto info = get_info(VK_EXT_SHADER_OBJECT_EXTENSION_NAME);',
                    '            if (info.state) {',
                    '                if (this->*(info.state) != kNotEnabled) {',
                    '                    for (auto interaction_ext : shader_object_interactions) {',
                    '                        info = get_info(interaction_ext);',
                    '                        assert(info.state);',
                    '                        if (this->*(info.state) != kEnabledByCreateinfo) {',
                    '                            this->*(info.state) = kEnabledByInteraction;',
                    '                        }',
                    '                    }',
                    '                }',
                    '            }',
                    '        }' ])
            struct.extend([
                '        return api_version;',
                '    }',
                '};'])

            # Output reference lists of instance/device extension names
            struct.extend(['', 'static const std::set<std::string> k%sExtensionNames = {' % type])
            struct.extend([Guarded(info['ifdef'], '    %s,' % info['define']) for ext_name, info in extension_items])
            struct.extend(['};', ''])
            output.extend(struct)

        return '\n'.join(output)

    #
    # Determine if a structure needs a safe_struct helper function
    # That is, it has an sType or one of its members is a pointer
    def NeedSafeStruct(self, structure):
        if 'VkBase' in structure.name:
            return False
        if 'sType' == structure.name:
            return True
        for member in structure.members:
            if member.ispointer == True:
                return True
        return False
    #
    # Combine safe struct helper source file preamble with body text and return
    def GenerateSafeStructHelperSource(self):
        safe_struct_helper_source = """
#include "vk_safe_struct.h"
#include "vk_typemap_helper.h"
#include "utils/vk_layer_utils.h"

#include <cstddef>
#include <cassert>
#include <cstring>
#include <vector>

#include <vulkan/vk_layer.h>

"""
        safe_struct_helper_source += self.GenerateSafeStructSource()

        return safe_struct_helper_source
    #
    # safe_struct source -- create bodies of safe struct helper functions
    def GenerateSafeStructSource(self):
        safe_struct_body = []
        wsi_structs = ['VkXlibSurfaceCreateInfoKHR',
                       'VkXcbSurfaceCreateInfoKHR',
                       'VkWaylandSurfaceCreateInfoKHR',
                       'VkAndroidSurfaceCreateInfoKHR',
                       'VkWin32SurfaceCreateInfoKHR',
                       'VkIOSSurfaceCreateInfoMVK',
                       'VkMacOSSurfaceCreateInfoMVK',
                       'VkMetalSurfaceCreateInfoEXT'
                       ]

        member_init_transforms = {
            'queueFamilyIndexCount': lambda m: f'{m.name}(0)'
        }

        def qfi_construct(item, member):
            true_index_setter = lambda i: f'{i}queueFamilyIndexCount = in_struct->queueFamilyIndexCount;\n'
            false_index_setter = lambda i: f'{i}queueFamilyIndexCount = 0;\n'
            if item.name == 'VkSwapchainCreateInfoKHR':
                return (f'(in_struct->imageSharingMode == VK_SHARING_MODE_CONCURRENT) && in_struct->{member.name}', true_index_setter, false_index_setter)
            else:
                return (f'(in_struct->sharingMode == VK_SHARING_MODE_CONCURRENT) && in_struct->{member.name}', true_index_setter, false_index_setter)

        # map of:
        #  <member name>: function(item, member) -> (condition, true statement, false statement)
        member_construct_conditions = {
            'pQueueFamilyIndices': qfi_construct
        }

        # For abstract types just want to save the pointer away
        # since we cannot make a copy.
        abstract_types = ['AHardwareBuffer',
                          'ANativeWindow',
                          'CAMetalLayer'
                         ]

        # Find what types of safe structs need to be generated based on output file name
        safe_struct_type_re = r'.*';
        if self.genOpts.filename.endswith('_khr.cpp'):
            safe_struct_type_re = r'.*KHR$'
        elif self.genOpts.filename.endswith('_ext.cpp'):
            safe_struct_type_re = r'.*EXT$'
        elif self.genOpts.filename.endswith('_vendor.cpp'):
            safe_struct_type_re = r'^(?!.*(KHR|EXT)$).*[A-Z]$' # Matches all words finishing with an upper case letter, but not ending with KHRor EXT
        else: # elif self.genOpts.filename.endswith('_core.cpp'):
            safe_struct_type_re = r'.*[a-z0-9]$'

        for item in self.structMembers:
            if self.NeedSafeStruct(item) == False:
                continue
            if item.name in wsi_structs:
                continue
            if not re.match(safe_struct_type_re, item.name):
                continue
            if item.ifdef_protect is not None:
                safe_struct_body.append("#ifdef %s\n" % item.ifdef_protect)
            ss_name = "safe_%s" % item.name
            init_list = ''          # list of members in struct constructor initializer
            default_init_list = ''  # Default constructor just inits ptrs to nullptr in initializer
            init_func_txt = ''      # Txt for initialize() function that takes struct ptr and inits members
            construct_txt = ''      # Body of constuctor as well as body of initialize() func following init_func_txt
            destruct_txt = ''

            custom_definitions = {
            # as_geom_khr_host_alloc maps a VkAccelerationStructureGeometryKHR to its host allocated instance array, if the user supplied such an array.
            'VkAccelerationStructureGeometryKHR':
"""
struct ASGeomKHRExtraData {
    ASGeomKHRExtraData(uint8_t *alloc, uint32_t primOffset, uint32_t primCount) :
        ptr(alloc),
        primitiveOffset(primOffset),
        primitiveCount(primCount)
    {}
    ~ASGeomKHRExtraData() {
        if (ptr)
            delete[] ptr;
    }
    uint8_t *ptr;
    uint32_t primitiveOffset;
    uint32_t primitiveCount;
};

vl_concurrent_unordered_map<const safe_VkAccelerationStructureGeometryKHR*, ASGeomKHRExtraData*, 4> as_geom_khr_host_alloc;"""
            }

            custom_defeault_construct_txt = {
                'VkDescriptorDataEXT' :
                    '    VkDescriptorType* pType = (VkDescriptorType*)&type_at_end[sizeof(VkDescriptorDataEXT)];\n'
                    '    *pType = VK_DESCRIPTOR_TYPE_MAX_ENUM;\n'
            }
            custom_construct_txt = {
                # VkWriteDescriptorSet is special case because pointers may be non-null but ignored
                'VkWriteDescriptorSet' :
                    '    switch (descriptorType) {\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLER:\n'
                    '        case VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER:\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE:\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:\n'
                    '        case VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT:\n'
                    '        case VK_DESCRIPTOR_TYPE_BLOCK_MATCH_IMAGE_QCOM:\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLE_WEIGHT_IMAGE_QCOM:\n'
                    '        if (descriptorCount && in_struct->pImageInfo) {\n'
                    '            pImageInfo = new VkDescriptorImageInfo[descriptorCount];\n'
                    '            for (uint32_t i = 0; i < descriptorCount; ++i) {\n'
                    '                pImageInfo[i] = in_struct->pImageInfo[i];\n'
                    '            }\n'
                    '        }\n'
                    '        break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER:\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER:\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC:\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC:\n'
                    '        if (descriptorCount && in_struct->pBufferInfo) {\n'
                    '            pBufferInfo = new VkDescriptorBufferInfo[descriptorCount];\n'
                    '            for (uint32_t i = 0; i < descriptorCount; ++i) {\n'
                    '                pBufferInfo[i] = in_struct->pBufferInfo[i];\n'
                    '            }\n'
                    '        }\n'
                    '        break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER:\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER:\n'
                    '        if (descriptorCount && in_struct->pTexelBufferView) {\n'
                    '            pTexelBufferView = new VkBufferView[descriptorCount];\n'
                    '            for (uint32_t i = 0; i < descriptorCount; ++i) {\n'
                    '                pTexelBufferView[i] = in_struct->pTexelBufferView[i];\n'
                    '            }\n'
                    '        }\n'
                    '        break;\n'
                    '        default:\n'
                    '        break;\n'
                    '    }\n',
                'VkShaderModuleCreateInfo' :
                    '    if (in_struct->pCode) {\n'
                    '        pCode = reinterpret_cast<uint32_t *>(new uint8_t[codeSize]);\n'
                    '        memcpy((void *)pCode, (void *)in_struct->pCode, codeSize);\n'
                    '    }\n',
                # VkGraphicsPipelineCreateInfo is special case because its pointers may be non-null but ignored
                'VkGraphicsPipelineCreateInfo' :
                    '    const bool is_graphics_library = LvlFindInChain<VkGraphicsPipelineLibraryCreateInfoEXT>(in_struct->pNext) != nullptr;\n'
                    '    if (stageCount && in_struct->pStages) {\n'
                    '        pStages = new safe_VkPipelineShaderStageCreateInfo[stageCount];\n'
                    '        for (uint32_t i = 0; i < stageCount; ++i) {\n'
                    '            pStages[i].initialize(&in_struct->pStages[i]);\n'
                    '        }\n'
                    '    }\n'
                    '    if (in_struct->pVertexInputState)\n'
                    '        pVertexInputState = new safe_VkPipelineVertexInputStateCreateInfo(in_struct->pVertexInputState);\n'
                    '    else\n'
                    '        pVertexInputState = nullptr;\n'
                    '    if (in_struct->pInputAssemblyState)\n'
                    '        pInputAssemblyState = new safe_VkPipelineInputAssemblyStateCreateInfo(in_struct->pInputAssemblyState);\n'
                    '    else\n'
                    '        pInputAssemblyState = nullptr;\n'
                    '    bool has_tessellation_stage = false;\n'
                    '    if (stageCount && pStages)\n'
                    '        for (uint32_t i = 0; i < stageCount && !has_tessellation_stage; ++i)\n'
                    '            if (pStages[i].stage == VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT || pStages[i].stage == VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT)\n'
                    '                has_tessellation_stage = true;\n'
                    '    if (in_struct->pTessellationState && has_tessellation_stage)\n'
                    '        pTessellationState = new safe_VkPipelineTessellationStateCreateInfo(in_struct->pTessellationState);\n'
                    '    else\n'
                    '        pTessellationState = nullptr; // original pTessellationState pointer ignored\n'
                    '    bool is_dynamic_has_rasterization = false;\n'
                    '    if (in_struct->pDynamicState && in_struct->pDynamicState->pDynamicStates) {\n'
                    '        for (uint32_t i = 0; i < in_struct->pDynamicState->dynamicStateCount && !is_dynamic_has_rasterization; ++i)\n'
                    '            if (in_struct->pDynamicState->pDynamicStates[i] == VK_DYNAMIC_STATE_RASTERIZER_DISCARD_ENABLE_EXT)\n'
                    '                is_dynamic_has_rasterization = true;\n'
                    '    }\n'
                    '    const bool has_rasterization = in_struct->pRasterizationState ? (is_dynamic_has_rasterization || !in_struct->pRasterizationState->rasterizerDiscardEnable) : false;\n'
                    '    if (in_struct->pViewportState && (has_rasterization || is_graphics_library)) {\n'
                    '        bool is_dynamic_viewports = false;\n'
                    '        bool is_dynamic_scissors = false;\n'
                    '        if (in_struct->pDynamicState && in_struct->pDynamicState->pDynamicStates) {\n'
                    '            for (uint32_t i = 0; i < in_struct->pDynamicState->dynamicStateCount && !is_dynamic_viewports; ++i)\n'
                    '                if (in_struct->pDynamicState->pDynamicStates[i] == VK_DYNAMIC_STATE_VIEWPORT)\n'
                    '                    is_dynamic_viewports = true;\n'
                    '            for (uint32_t i = 0; i < in_struct->pDynamicState->dynamicStateCount && !is_dynamic_scissors; ++i)\n'
                    '                if (in_struct->pDynamicState->pDynamicStates[i] == VK_DYNAMIC_STATE_SCISSOR)\n'
                    '                    is_dynamic_scissors = true;\n'
                    '        }\n'
                    '        pViewportState = new safe_VkPipelineViewportStateCreateInfo(in_struct->pViewportState, is_dynamic_viewports, is_dynamic_scissors);\n'
                    '    } else\n'
                    '        pViewportState = nullptr; // original pViewportState pointer ignored\n'
                    '    if (in_struct->pRasterizationState)\n'
                    '        pRasterizationState = new safe_VkPipelineRasterizationStateCreateInfo(in_struct->pRasterizationState);\n'
                    '    else\n'
                    '        pRasterizationState = nullptr;\n'
                    '    if (in_struct->pMultisampleState && (renderPass != VK_NULL_HANDLE || has_rasterization || is_graphics_library))\n'
                    '        pMultisampleState = new safe_VkPipelineMultisampleStateCreateInfo(in_struct->pMultisampleState);\n'
                    '    else\n'
                    '        pMultisampleState = nullptr; // original pMultisampleState pointer ignored\n'
                    '    // needs a tracked subpass state uses_depthstencil_attachment\n'
                    '    if (in_struct->pDepthStencilState && ((has_rasterization && uses_depthstencil_attachment) || is_graphics_library))\n'
                    '        pDepthStencilState = new safe_VkPipelineDepthStencilStateCreateInfo(in_struct->pDepthStencilState);\n'
                    '    else\n'
                    '        pDepthStencilState = nullptr; // original pDepthStencilState pointer ignored\n'
                    '    // needs a tracked subpass state usesColorAttachment\n'
                    '    if (in_struct->pColorBlendState && ((has_rasterization && uses_color_attachment) || is_graphics_library))\n'
                    '        pColorBlendState = new safe_VkPipelineColorBlendStateCreateInfo(in_struct->pColorBlendState);\n'
                    '    else\n'
                    '        pColorBlendState = nullptr; // original pColorBlendState pointer ignored\n'
                    '    if (in_struct->pDynamicState)\n'
                    '        pDynamicState = new safe_VkPipelineDynamicStateCreateInfo(in_struct->pDynamicState);\n'
                    '    else\n'
                    '        pDynamicState = nullptr;\n',
                 # VkPipelineViewportStateCreateInfo is special case because its pointers may be non-null but ignored
                'VkPipelineViewportStateCreateInfo' :
                    '    if (in_struct->pViewports && !is_dynamic_viewports) {\n'
                    '        pViewports = new VkViewport[in_struct->viewportCount];\n'
                    '        memcpy ((void *)pViewports, (void *)in_struct->pViewports, sizeof(VkViewport)*in_struct->viewportCount);\n'
                    '    }\n'
                    '    else\n'
                    '        pViewports = nullptr;\n'
                    '    if (in_struct->pScissors && !is_dynamic_scissors) {\n'
                    '        pScissors = new VkRect2D[in_struct->scissorCount];\n'
                    '        memcpy ((void *)pScissors, (void *)in_struct->pScissors, sizeof(VkRect2D)*in_struct->scissorCount);\n'
                    '    }\n'
                    '    else\n'
                    '        pScissors = nullptr;\n',
                # VkFrameBufferCreateInfo is special case because its pAttachments pointer may be non-null but ignored
                'VkFramebufferCreateInfo' :
                    '    if (attachmentCount && in_struct->pAttachments && !(flags & VK_FRAMEBUFFER_CREATE_IMAGELESS_BIT)) {\n'
                    '        pAttachments = new VkImageView[attachmentCount];\n'
                    '        for (uint32_t i = 0; i < attachmentCount; ++i) {\n'
                    '            pAttachments[i] = in_struct->pAttachments[i];\n'
                    '        }\n'
                    '    }\n',
                # VkDescriptorSetLayoutBinding is special case because its pImmutableSamplers pointer may be non-null but ignored
                'VkDescriptorSetLayoutBinding' :
                    '    const bool sampler_type = in_struct->descriptorType == VK_DESCRIPTOR_TYPE_SAMPLER || in_struct->descriptorType == VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;\n'
                    '    if (descriptorCount && in_struct->pImmutableSamplers && sampler_type) {\n'
                    '        pImmutableSamplers = new VkSampler[descriptorCount];\n'
                    '        for (uint32_t i = 0; i < descriptorCount; ++i) {\n'
                    '            pImmutableSamplers[i] = in_struct->pImmutableSamplers[i];\n'
                    '        }\n'
                    '    }\n',
                'VkAccelerationStructureBuildGeometryInfoKHR':
                    '    if (geometryCount) {\n'
                    '        if ( in_struct->ppGeometries) {\n'
                    '            ppGeometries = new safe_VkAccelerationStructureGeometryKHR *[geometryCount];\n'
                    '            for (uint32_t i = 0; i < geometryCount; ++i) {\n'
                    '                ppGeometries[i] = new safe_VkAccelerationStructureGeometryKHR(in_struct->ppGeometries[i], is_host, &build_range_infos[i]);\n'
                    '            }\n'
                    '        } else {\n'
                    '            pGeometries = new safe_VkAccelerationStructureGeometryKHR[geometryCount];\n'
                    '            for (uint32_t i = 0; i < geometryCount; ++i) {\n'
                    '                (pGeometries)[i] = safe_VkAccelerationStructureGeometryKHR(&(in_struct->pGeometries)[i], is_host, &build_range_infos[i]);\n'
                    '            }\n'
                    '        }\n'
                    '    }\n',
                'VkAccelerationStructureGeometryKHR':
                    '    if (is_host && geometryType == VK_GEOMETRY_TYPE_INSTANCES_KHR) {\n'
                    '        if (geometry.instances.arrayOfPointers) {\n'
                    '            size_t pp_array_size = build_range_info->primitiveCount * sizeof(VkAccelerationStructureInstanceKHR*);\n'
                    '            size_t p_array_size = build_range_info->primitiveCount * sizeof(VkAccelerationStructureInstanceKHR);\n'
                    '            size_t array_size = build_range_info->primitiveOffset + pp_array_size + p_array_size;\n'
                    '            uint8_t *allocation = new uint8_t[array_size];\n'
                    '            VkAccelerationStructureInstanceKHR **ppInstances = reinterpret_cast<VkAccelerationStructureInstanceKHR **>(allocation + build_range_info->primitiveOffset);\n'
                    '            VkAccelerationStructureInstanceKHR *pInstances = reinterpret_cast<VkAccelerationStructureInstanceKHR *>(allocation + build_range_info->primitiveOffset + pp_array_size);\n'
                    '            for (uint32_t i = 0; i < build_range_info->primitiveCount; ++i) {\n'
                    '                const uint8_t *byte_ptr = reinterpret_cast<const uint8_t *>(in_struct->geometry.instances.data.hostAddress);\n'
                    '                pInstances[i] = *(reinterpret_cast<VkAccelerationStructureInstanceKHR * const*>(byte_ptr + build_range_info->primitiveOffset)[i]);\n'
                    '                ppInstances[i] = &pInstances[i];\n'
                    '            }\n'
                    '            geometry.instances.data.hostAddress = allocation;\n'
                    '            as_geom_khr_host_alloc.insert(this, new ASGeomKHRExtraData(allocation, build_range_info->primitiveOffset, build_range_info->primitiveCount));\n'
                    '        } else {\n'
                    '            const auto primitive_offset = build_range_info->primitiveOffset;\n'
                    '            const auto primitive_count = build_range_info->primitiveCount;\n'
                    '            size_t array_size = primitive_offset + primitive_count * sizeof(VkAccelerationStructureInstanceKHR);\n'
                    '            uint8_t *allocation = new uint8_t[array_size];\n'
                    '            auto host_address = static_cast<const uint8_t*>(in_struct->geometry.instances.data.hostAddress);\n'
                    '            memcpy(allocation + primitive_offset, host_address + primitive_offset, primitive_count * sizeof(VkAccelerationStructureInstanceKHR));\n'
                    '            geometry.instances.data.hostAddress = allocation;\n'
                    '            as_geom_khr_host_alloc.insert(this, new ASGeomKHRExtraData(allocation, build_range_info->primitiveOffset, build_range_info->primitiveCount));\n'
                    '        }\n'
                    '    }\n',
                'VkMicromapBuildInfoEXT':
                    '    if (in_struct->pUsageCounts) {\n'
                    '        pUsageCounts = new VkMicromapUsageEXT[in_struct->usageCountsCount];\n'
                    '        memcpy ((void *)pUsageCounts, (void *)in_struct->pUsageCounts, sizeof(VkMicromapUsageEXT)*in_struct->usageCountsCount);\n'
                    '    }\n'
                    '    if (in_struct->ppUsageCounts) {\n'
                    '        VkMicromapUsageEXT** pointer_array  = new VkMicromapUsageEXT*[in_struct->usageCountsCount];\n'
                    '        for (uint32_t i = 0; i < in_struct->usageCountsCount; ++i) {\n'
                    '            pointer_array[i] = new VkMicromapUsageEXT(*in_struct->ppUsageCounts[i]);\n'
                    '        }\n'
                    '        ppUsageCounts = pointer_array;\n'
                    '    }\n',
                'VkAccelerationStructureTrianglesOpacityMicromapEXT':
                    '    if (in_struct->pUsageCounts) {\n'
                    '        pUsageCounts = new VkMicromapUsageEXT[in_struct->usageCountsCount];\n'
                    '        memcpy ((void *)pUsageCounts, (void *)in_struct->pUsageCounts, sizeof(VkMicromapUsageEXT)*in_struct->usageCountsCount);\n'
                    '    }\n'
                    '    if (in_struct->ppUsageCounts) {\n'
                    '        VkMicromapUsageEXT** pointer_array = new VkMicromapUsageEXT*[in_struct->usageCountsCount];\n'
                    '        for (uint32_t i = 0; i < in_struct->usageCountsCount; ++i) {\n'
                    '            pointer_array[i] = new VkMicromapUsageEXT(*in_struct->ppUsageCounts[i]);\n'
                    '        }\n'
                    '        ppUsageCounts = pointer_array;\n'
                    '    }\n',
                'VkAccelerationStructureTrianglesDisplacementMicromapNV':
                    '    if (in_struct->pUsageCounts) {\n'
                    '        pUsageCounts = new VkMicromapUsageEXT[in_struct->usageCountsCount];\n'
                    '        memcpy ((void *)pUsageCounts, (void *)in_struct->pUsageCounts, sizeof(VkMicromapUsageEXT)*in_struct->usageCountsCount);\n'
                    '    }\n'
                    '    if (in_struct->ppUsageCounts) {\n'
                    '        VkMicromapUsageEXT** pointer_array = new VkMicromapUsageEXT*[in_struct->usageCountsCount];\n'
                    '        for (uint32_t i = 0; i < in_struct->usageCountsCount; ++i) {\n'
                    '            pointer_array[i] = new VkMicromapUsageEXT(*in_struct->ppUsageCounts[i]);\n'
                    '        }\n'
                    '        ppUsageCounts = pointer_array;\n'
                    '    }\n',
                'VkDescriptorDataEXT' :
                    '    VkDescriptorType* pType = (VkDescriptorType*)&type_at_end[sizeof(VkDescriptorDataEXT)];\n'
                    '\n'
                    '    switch (type)\n'
                    '    {\n'
                    '        case VK_DESCRIPTOR_TYPE_MAX_ENUM:                   break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLER:                    pSampler              = new VkSampler(*in_struct->pSampler); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER:     pCombinedImageSampler = new VkDescriptorImageInfo(*in_struct->pCombinedImageSampler); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE:              pSampledImage         = in_struct->pSampledImage ? new VkDescriptorImageInfo(*in_struct->pSampledImage) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:              pStorageImage         = in_struct->pStorageImage ? new VkDescriptorImageInfo(*in_struct->pStorageImage) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT:           pInputAttachmentImage = new VkDescriptorImageInfo(*in_struct->pInputAttachmentImage); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER:       pUniformTexelBuffer   = in_struct->pUniformTexelBuffer ? new safe_VkDescriptorAddressInfoEXT(in_struct->pUniformTexelBuffer) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER:       pStorageTexelBuffer   = in_struct->pStorageTexelBuffer ? new safe_VkDescriptorAddressInfoEXT(in_struct->pStorageTexelBuffer) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER:             pUniformBuffer        = in_struct->pUniformBuffer ? new safe_VkDescriptorAddressInfoEXT(in_struct->pUniformBuffer) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER:             pStorageBuffer        = in_struct->pStorageBuffer ? new safe_VkDescriptorAddressInfoEXT(in_struct->pStorageBuffer) : nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR: accelerationStructure = in_struct->accelerationStructure; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_NV:  accelerationStructure = in_struct->accelerationStructure; break;\n'
                    '        default:                                            break;\n'
                    '    }\n'
                    '\n'
                    '    *pType = type;\n',
                'VkPipelineRenderingCreateInfo': '''
    bool custom_init = copy_state && copy_state->init;
    if (custom_init) {
        custom_init = copy_state->init(reinterpret_cast<VkBaseOutStructure*>(this), reinterpret_cast<const VkBaseOutStructure*>(in_struct));
    }
    if (!custom_init) {
        // The custom iniitalization was not used, so do the regular initialization
        if (in_struct->pColorAttachmentFormats) {
            pColorAttachmentFormats = new VkFormat[in_struct->colorAttachmentCount];
            memcpy ((void *)pColorAttachmentFormats, (void *)in_struct->pColorAttachmentFormats, sizeof(VkFormat)*in_struct->colorAttachmentCount);
        }
    }
'''
            }

            custom_copy_txt = {
                # VkGraphicsPipelineCreateInfo is special case because it has custom construct parameters
                'VkGraphicsPipelineCreateInfo' :
                    '    pNext = SafePnextCopy(copy_src.pNext);\n'
                    '    const bool is_graphics_library = LvlFindInChain<VkGraphicsPipelineLibraryCreateInfoEXT>(copy_src.pNext);\n'
                    '    if (stageCount && copy_src.pStages) {\n'
                    '        pStages = new safe_VkPipelineShaderStageCreateInfo[stageCount];\n'
                    '        for (uint32_t i = 0; i < stageCount; ++i) {\n'
                    '            pStages[i].initialize(&copy_src.pStages[i]);\n'
                    '        }\n'
                    '    }\n'
                    '    if (copy_src.pVertexInputState)\n'
                    '        pVertexInputState = new safe_VkPipelineVertexInputStateCreateInfo(*copy_src.pVertexInputState);\n'
                    '    else\n'
                    '        pVertexInputState = nullptr;\n'
                    '    if (copy_src.pInputAssemblyState)\n'
                    '        pInputAssemblyState = new safe_VkPipelineInputAssemblyStateCreateInfo(*copy_src.pInputAssemblyState);\n'
                    '    else\n'
                    '        pInputAssemblyState = nullptr;\n'
                    '    bool has_tessellation_stage = false;\n'
                    '    if (stageCount && pStages)\n'
                    '        for (uint32_t i = 0; i < stageCount && !has_tessellation_stage; ++i)\n'
                    '            if (pStages[i].stage == VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT || pStages[i].stage == VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT)\n'
                    '                has_tessellation_stage = true;\n'
                    '    if (copy_src.pTessellationState && has_tessellation_stage)\n'
                    '        pTessellationState = new safe_VkPipelineTessellationStateCreateInfo(*copy_src.pTessellationState);\n'
                    '    else\n'
                    '        pTessellationState = nullptr; // original pTessellationState pointer ignored\n'
                    '    bool is_dynamic_has_rasterization = false;\n'
                    '    if (copy_src.pDynamicState && copy_src.pDynamicState->pDynamicStates) {\n'
                    '        for (uint32_t i = 0; i < copy_src.pDynamicState->dynamicStateCount && !is_dynamic_has_rasterization; ++i)\n'
                    '            if (copy_src.pDynamicState->pDynamicStates[i] == VK_DYNAMIC_STATE_RASTERIZER_DISCARD_ENABLE_EXT)\n'
                    '                is_dynamic_has_rasterization = true;\n'
                    '    }\n'
                    '    const bool has_rasterization = copy_src.pRasterizationState ? (is_dynamic_has_rasterization || !copy_src.pRasterizationState->rasterizerDiscardEnable) : false;\n'
                    '    if (copy_src.pViewportState && (has_rasterization || is_graphics_library)) {\n'
                    '        pViewportState = new safe_VkPipelineViewportStateCreateInfo(*copy_src.pViewportState);\n'
                    '    } else\n'
                    '        pViewportState = nullptr; // original pViewportState pointer ignored\n'
                    '    if (copy_src.pRasterizationState)\n'
                    '        pRasterizationState = new safe_VkPipelineRasterizationStateCreateInfo(*copy_src.pRasterizationState);\n'
                    '    else\n'
                    '        pRasterizationState = nullptr;\n'
                    '    if (copy_src.pMultisampleState && (has_rasterization || is_graphics_library))\n'
                    '        pMultisampleState = new safe_VkPipelineMultisampleStateCreateInfo(*copy_src.pMultisampleState);\n'
                    '    else\n'
                    '        pMultisampleState = nullptr; // original pMultisampleState pointer ignored\n'
                    '    if (copy_src.pDepthStencilState && (has_rasterization || is_graphics_library))\n'
                    '        pDepthStencilState = new safe_VkPipelineDepthStencilStateCreateInfo(*copy_src.pDepthStencilState);\n'
                    '    else\n'
                    '        pDepthStencilState = nullptr; // original pDepthStencilState pointer ignored\n'
                    '    if (copy_src.pColorBlendState && (has_rasterization || is_graphics_library))\n'
                    '        pColorBlendState = new safe_VkPipelineColorBlendStateCreateInfo(*copy_src.pColorBlendState);\n'
                    '    else\n'
                    '        pColorBlendState = nullptr; // original pColorBlendState pointer ignored\n'
                    '    if (copy_src.pDynamicState)\n'
                    '        pDynamicState = new safe_VkPipelineDynamicStateCreateInfo(*copy_src.pDynamicState);\n'
                    '    else\n'
                    '        pDynamicState = nullptr;\n',
                 # VkPipelineViewportStateCreateInfo is special case because it has custom construct parameters
                'VkPipelineViewportStateCreateInfo' :
                    '    pNext = SafePnextCopy(copy_src.pNext);\n'
                    '    if (copy_src.pViewports) {\n'
                    '        pViewports = new VkViewport[copy_src.viewportCount];\n'
                    '        memcpy ((void *)pViewports, (void *)copy_src.pViewports, sizeof(VkViewport)*copy_src.viewportCount);\n'
                    '    }\n'
                    '    else\n'
                    '        pViewports = nullptr;\n'
                    '    if (copy_src.pScissors) {\n'
                    '        pScissors = new VkRect2D[copy_src.scissorCount];\n'
                    '        memcpy ((void *)pScissors, (void *)copy_src.pScissors, sizeof(VkRect2D)*copy_src.scissorCount);\n'
                    '    }\n'
                    '    else\n'
                    '        pScissors = nullptr;\n',
                'VkFramebufferCreateInfo' :
                    '    pNext = SafePnextCopy(copy_src.pNext);\n'
                    '    if (attachmentCount && copy_src.pAttachments && !(flags & VK_FRAMEBUFFER_CREATE_IMAGELESS_BIT)) {\n'
                    '        pAttachments = new VkImageView[attachmentCount];\n'
                    '        for (uint32_t i = 0; i < attachmentCount; ++i) {\n'
                    '            pAttachments[i] = copy_src.pAttachments[i];\n'
                    '        }\n'
                    '    }\n',
                'VkAccelerationStructureBuildGeometryInfoKHR':
                    '    if (geometryCount) {\n'
                    '        if ( copy_src.ppGeometries) {\n'
                    '            ppGeometries = new safe_VkAccelerationStructureGeometryKHR *[geometryCount];\n'
                    '            for (uint32_t i = 0; i < geometryCount; ++i) {\n'
                    '                ppGeometries[i] = new safe_VkAccelerationStructureGeometryKHR(*copy_src.ppGeometries[i]);\n'
                    '            }\n'
                    '        } else {\n'
                    '            pGeometries = new safe_VkAccelerationStructureGeometryKHR[geometryCount];\n'
                    '            for (uint32_t i = 0; i < geometryCount; ++i) {\n'
                    '                pGeometries[i] = safe_VkAccelerationStructureGeometryKHR(copy_src.pGeometries[i]);\n'
                    '            }\n'
                    '        }\n'
                    '    }\n',
                'VkAccelerationStructureGeometryKHR':
                    '    pNext = SafePnextCopy(copy_src.pNext);\n'
                    '    auto src_iter = as_geom_khr_host_alloc.find(&copy_src);\n'
                    '    if (src_iter != as_geom_khr_host_alloc.end()) {\n'
                    '        auto &src_alloc = src_iter->second;\n'
                    '        if (geometry.instances.arrayOfPointers) {\n'
                    '            size_t pp_array_size = src_alloc->primitiveCount * sizeof(VkAccelerationStructureInstanceKHR*);\n'
                    '            size_t p_array_size = src_alloc->primitiveCount * sizeof(VkAccelerationStructureInstanceKHR);\n'
                    '            size_t array_size = src_alloc->primitiveOffset + pp_array_size + p_array_size;\n'
                    '            uint8_t *allocation = new uint8_t[array_size];\n'
                    '            VkAccelerationStructureInstanceKHR **ppInstances = reinterpret_cast<VkAccelerationStructureInstanceKHR **>(allocation + src_alloc->primitiveOffset);\n'
                    '            VkAccelerationStructureInstanceKHR *pInstances = reinterpret_cast<VkAccelerationStructureInstanceKHR *>(allocation + src_alloc->primitiveOffset + pp_array_size);\n'
                    '            for (uint32_t i = 0; i < src_alloc->primitiveCount; ++i) {\n'
                    '                pInstances[i] = *(reinterpret_cast<VkAccelerationStructureInstanceKHR * const*>(src_alloc->ptr + src_alloc->primitiveOffset)[i]);\n'
                    '                ppInstances[i] = &pInstances[i];\n'
                    '            }\n'
                    '            geometry.instances.data.hostAddress = allocation;\n'
                    '            as_geom_khr_host_alloc.insert(this, new ASGeomKHRExtraData(allocation, src_alloc->primitiveOffset, src_alloc->primitiveCount));\n'
                    '        } else {\n'
                    '            size_t array_size = src_alloc->primitiveOffset + src_alloc->primitiveCount * sizeof(VkAccelerationStructureInstanceKHR);\n'
                    '            uint8_t *allocation = new uint8_t[array_size];\n'
                    '            memcpy(allocation, src_alloc->ptr, array_size);\n'
                    '            geometry.instances.data.hostAddress = allocation;\n'
                    '            as_geom_khr_host_alloc.insert(this, new ASGeomKHRExtraData(allocation, src_alloc->primitiveOffset, src_alloc->primitiveCount));\n'
                    '        }\n'
                    '    }\n',
                'VkDescriptorDataEXT' :
                    '    VkDescriptorType* pType = (VkDescriptorType*)&type_at_end[sizeof(VkDescriptorDataEXT)];\n'
                    '    VkDescriptorType type = *(VkDescriptorType*)&copy_src.type_at_end[sizeof(VkDescriptorDataEXT)];\n'
                    '\n'
                    '    switch (type)\n'
                    '    {\n'
                    '        case VK_DESCRIPTOR_TYPE_MAX_ENUM:                   break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLER:                    pSampler              = new VkSampler(*copy_src.pSampler); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER:     pCombinedImageSampler = new VkDescriptorImageInfo(*copy_src.pCombinedImageSampler); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE:              pSampledImage         = new VkDescriptorImageInfo(*copy_src.pSampledImage); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:              pStorageImage         = new VkDescriptorImageInfo(*copy_src.pStorageImage); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT:           pInputAttachmentImage = new VkDescriptorImageInfo(*copy_src.pInputAttachmentImage); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER:       pUniformTexelBuffer   = new safe_VkDescriptorAddressInfoEXT(*copy_src.pUniformTexelBuffer); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER:       pStorageTexelBuffer   = new safe_VkDescriptorAddressInfoEXT(*copy_src.pStorageTexelBuffer); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER:             pUniformBuffer        = new safe_VkDescriptorAddressInfoEXT(*copy_src.pUniformBuffer); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER:             pStorageBuffer        = new safe_VkDescriptorAddressInfoEXT(*copy_src.pStorageBuffer); break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR: accelerationStructure = copy_src.accelerationStructure; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_NV:  accelerationStructure = copy_src.accelerationStructure; break;\n'
                    '        default:                                            break;\n'
                    '    }\n'
                    '\n'
                    '    *pType = type;\n',
                'VkPipelineRenderingCreateInfo': '''
    if (copy_src.pColorAttachmentFormats) {
        pColorAttachmentFormats = new VkFormat[copy_src.colorAttachmentCount];
        memcpy ((void *)pColorAttachmentFormats, (void *)copy_src.pColorAttachmentFormats, sizeof(VkFormat)*copy_src.colorAttachmentCount);
    }
'''
            }

            custom_destruct_txt = {
                'VkShaderModuleCreateInfo' :
                    '    if (pCode)\n'
                    '        delete[] reinterpret_cast<const uint8_t *>(pCode);\n',
                'VkAccelerationStructureBuildGeometryInfoKHR' :
                    '    if (ppGeometries) {\n'
                    '        for (uint32_t i = 0; i < geometryCount; ++i) {\n'
                    '             delete ppGeometries[i];\n'
                    '        }\n'
                    '        delete[] ppGeometries;\n'
                    '    } else if(pGeometries) {\n'
                    '        delete[] pGeometries;\n'
                    '    }\n',
                'VkAccelerationStructureGeometryKHR':
                    '    auto iter = as_geom_khr_host_alloc.pop(this);\n'
                    '    if (iter != as_geom_khr_host_alloc.end()) {\n'
                    '        delete iter->second;\n'
                    '    }\n',
                'VkMicromapBuildInfoEXT':
                    '    if (pUsageCounts)\n'
                    '        delete[] pUsageCounts;\n'
                    '    if (ppUsageCounts) {\n'
                    '        for (uint32_t i = 0; i < usageCountsCount; ++i) {\n'
                    '             delete ppUsageCounts[i];\n'
                    '        }\n'
                    '        delete[] ppUsageCounts;\n'
                    '    }\n',
                'VkAccelerationStructureTrianglesOpacityMicromapEXT':
                    '    if (pUsageCounts)\n'
                    '        delete[] pUsageCounts;\n'
                    '    if (ppUsageCounts) {\n'
                    '        for (uint32_t i = 0; i < usageCountsCount; ++i) {\n'
                    '             delete ppUsageCounts[i];\n'
                    '        }\n'
                    '        delete[] ppUsageCounts;\n'
                    '    }\n',
                'VkAccelerationStructureTrianglesDisplacementMicromapNV':
                    '    if (pUsageCounts)\n'
                    '        delete[] pUsageCounts;\n'
                    '    if (ppUsageCounts) {\n'
                    '        for (uint32_t i = 0; i < usageCountsCount; ++i) {\n'
                    '             delete ppUsageCounts[i];\n'
                    '        }\n'
                    '        delete[] ppUsageCounts;\n'
                    '    }\n',
                'VkDescriptorDataEXT' :
                    '\n'
                    '    VkDescriptorType& thisType = *(VkDescriptorType*)&type_at_end[sizeof(VkDescriptorDataEXT)];\n'
                    '\n'
                    '    switch (thisType)\n'
                    '    {\n'
                    '        case VK_DESCRIPTOR_TYPE_MAX_ENUM:                   break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC:     break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLER:                    delete pSampler;              pSampler              = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER:     delete pCombinedImageSampler; pCombinedImageSampler = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE:              delete pSampledImage;         pSampledImage         = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:              delete pStorageImage;         pStorageImage         = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT:           delete pInputAttachmentImage; pInputAttachmentImage = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER:       delete pUniformTexelBuffer;   pUniformTexelBuffer   = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER:       delete pStorageTexelBuffer;   pStorageTexelBuffer   = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER:             delete pUniformBuffer;        pUniformBuffer        = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_STORAGE_BUFFER:             delete pStorageBuffer;        pStorageBuffer        = nullptr; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR: accelerationStructure = 0ull; break;\n'
                    '        case VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_NV:  accelerationStructure = 0ull; break;\n'
                    '        default:                                            break;\n'
                    '    }\n'
                    '\n'
                    '    thisType = VK_DESCRIPTOR_TYPE_MAX_ENUM;\n',
            }
            copy_pnext = ''
            copy_strings = ''
            for member in item.members:
                m_type = member.type
                if member.name == 'pNext':
                    copy_pnext = '    pNext = SafePnextCopy(in_struct->pNext, copy_state);\n'
                if member.type in self.structNames:
                    member_index = next((i for i, v in enumerate(self.structMembers) if v[0] == member.type), None)
                    if member_index is not None and self.NeedSafeStruct(self.structMembers[member_index]) == True:
                        m_type = 'safe_%s' % member.type
                if member.ispointer and 'safe_' not in m_type and self.TypeContainsObjectHandle(member.type, False) == False:
                    # Ptr types w/o a safe_struct, for non-null case need to allocate new ptr and copy data in
                    if m_type in ['void', 'char']:
                        if member.name != 'pNext':
                            if m_type == 'char':
                                # Create deep copies of strings
                                if member.len:
                                    copy_strings += '    char **tmp_%s = new char *[in_struct->%s];\n' % (member.name, member.len)
                                    copy_strings += '    for (uint32_t i = 0; i < %s; ++i) {\n' % member.len
                                    copy_strings += '        tmp_%s[i] = SafeStringCopy(in_struct->%s[i]);\n' % (member.name, member.name)
                                    copy_strings += '    }\n'
                                    copy_strings += '    %s = tmp_%s;\n' % (member.name, member.name)

                                    destruct_txt += '    if (%s) {\n' % member.name
                                    destruct_txt += '        for (uint32_t i = 0; i < %s; ++i) {\n' % member.len
                                    destruct_txt += '            delete [] %s[i];\n' % member.name
                                    destruct_txt += '        }\n'
                                    destruct_txt += '        delete [] %s;\n' % member.name
                                    destruct_txt += '    }\n'
                                else:
                                    copy_strings += '    %s = SafeStringCopy(in_struct->%s);\n' % (member.name, member.name)
                                    destruct_txt += '    if (%s) delete [] %s;\n' % (member.name, member.name)
                            else:
                                # We need a deep copy of pData / dataSize combos
                                if member.name == 'pData':
                                    init_list += '\n    %s(nullptr),' % (member.name)
                                    construct_txt += '    if (in_struct->pData != nullptr) {\n'
                                    construct_txt += '        auto temp = new std::byte[in_struct->dataSize];\n'
                                    construct_txt += '        std::memcpy(temp, in_struct->pData, in_struct->dataSize);\n'
                                    construct_txt += '        pData = temp;\n'
                                    construct_txt += '    }\n'

                                    destruct_txt  += '    if (pData != nullptr) {\n'
                                    destruct_txt  += '        auto temp = reinterpret_cast<const std::byte*>(pData);\n'
                                    destruct_txt  += '        delete [] temp;\n'
                                    destruct_txt  += '    }\n'
                                else:
                                    init_list += '\n    %s(in_struct->%s),' % (member.name, member.name)
                                    init_func_txt += '    %s = in_struct->%s;\n' % (member.name, member.name)
                        default_init_list += '\n    %s(nullptr),' % (member.name)
                    else:
                        default_init_list += '\n    %s(nullptr),' % (member.name)
                        init_list += '\n    %s(nullptr),' % (member.name)
                        if m_type in abstract_types:
                            construct_txt += '    %s = in_struct->%s;\n' % (member.name, member.name)
                        else:
                            init_func_txt += '    %s = nullptr;\n' % (member.name)
                            if not member.isstaticarray and (member.len is None or '/' in member.len):
                                construct_txt += '    if (in_struct->%s) {\n' % member.name
                                construct_txt += '        %s = new %s(*in_struct->%s);\n' % (member.name, m_type, member.name)
                                construct_txt += '    }\n'
                                destruct_txt += '    if (%s)\n' % member.name
                                destruct_txt += '        delete %s;\n' % member.name
                            else:
                                # Prepend struct members with struct name
                                decorated_length = member.len
                                for other_member in item.members:
                                    decorated_length = re.sub(r'\b({})\b'.format(other_member.name), r'in_struct->\1', decorated_length)
                                try:
                                    concurrent_clause = member_construct_conditions[member.name](item, member)
                                except:
                                    concurrent_clause = (f'in_struct->{member.name}', lambda x: '')
                                construct_txt += f'    if ({concurrent_clause[0]}) {{' + '\n'
                                construct_txt += '        %s = new %s[%s];\n' % (member.name, m_type, decorated_length)
                                construct_txt += '        memcpy ((void *)%s, (void *)in_struct->%s, sizeof(%s)*%s);\n' % (member.name, member.name, m_type, decorated_length)
                                construct_txt += concurrent_clause[1]('        ')
                                if len(concurrent_clause) > 2:
                                    construct_txt += '    } else {\n'
                                    construct_txt += concurrent_clause[2]('        ')
                                construct_txt += '    }\n'
                                destruct_txt += '    if (%s)\n' % member.name
                                destruct_txt += '        delete[] %s;\n' % member.name
                elif member.isstaticarray or member.len is not None:
                    if member.len is None:
                        # Extract length of static array by grabbing val between []
                        static_array_size = re.match(r"[^[]*\[([^]]*)\]", member.cdecl)
                        construct_txt += '    for (uint32_t i = 0; i < %s; ++i) {\n' % static_array_size.group(1)
                        construct_txt += '        %s[i] = in_struct->%s[i];\n' % (member.name, member.name)
                        construct_txt += '    }\n'
                    else:
                        # Init array ptr to NULL
                        default_init_list += '\n    %s(nullptr),' % member.name
                        init_list += '\n    %s(nullptr),' % member.name
                        init_func_txt += '    %s = nullptr;\n' % member.name
                        array_element = 'in_struct->%s[i]' % member.name
                        if member.type in self.structNames:
                            member_index = next((i for i, v in enumerate(self.structMembers) if v[0] == member.type), None)
                            if member_index is not None and self.NeedSafeStruct(self.structMembers[member_index]) == True:
                                array_element = '%s(&in_struct->safe_%s[i])' % (member.type, member.name)
                        construct_txt += '    if (%s && in_struct->%s) {\n' % (member.len, member.name)
                        construct_txt += '        %s = new %s[%s];\n' % (member.name, m_type, member.len)
                        destruct_txt += '    if (%s)\n' % member.name
                        destruct_txt += '        delete[] %s;\n' % member.name
                        construct_txt += '        for (uint32_t i = 0; i < %s; ++i) {\n' % (member.len)
                        if 'safe_' in m_type:
                            construct_txt += '            %s[i].initialize(&in_struct->%s[i]);\n' % (member.name, member.name)
                        else:
                            construct_txt += '            %s[i] = %s;\n' % (member.name, array_element)
                        construct_txt += '        }\n'
                        construct_txt += '    }\n'
                elif member.ispointer == True:
                    default_init_list += '\n    %s(nullptr),' % (member.name)
                    init_list += '\n    %s(nullptr),' % (member.name)
                    init_func_txt += '    %s = nullptr;\n' % (member.name)
                    construct_txt += '    if (in_struct->%s)\n' % member.name
                    construct_txt += '        %s = new %s(in_struct->%s);\n' % (member.name, m_type, member.name)
                    destruct_txt += '    if (%s)\n' % member.name
                    destruct_txt += '        delete %s;\n' % member.name
                elif 'safe_' in m_type and member.type == 'VkDescriptorDataEXT':
                    init_list += '\n    %s(&in_struct->%s, in_struct->type),' % (member.name, member.name)
                    init_func_txt += '    %s.initialize(&in_struct->%s, in_struct->type);\n' % (member.name, member.name)
                elif 'safe_' in m_type:
                    init_list += '\n    %s(&in_struct->%s),' % (member.name, member.name)
                    init_func_txt += '    %s.initialize(&in_struct->%s);\n' % (member.name, member.name)
                else:
                    try:
                        init_list += f'\n    {member_init_transforms[member.name](member)},'
                    except:
                        init_list += '\n    %s(in_struct->%s),' % (member.name, member.name)
                        init_func_txt += '    %s = in_struct->%s;\n' % (member.name, member.name)
                    if (self.structOrUnion[item.name] != 'union'):
                        if member.name == 'sType' and item.name in self.structTypes:
                            default_init_list += f'\n    {member.name}({self.structTypes[item.name].value}),'
                        else:
                            default_init_list += f'\n    {member.name}(),'
            if '' != init_list:
                init_list = init_list[:-1] # hack off final comma

            if item.name in custom_definitions:
                safe_struct_body.append(custom_definitions[item.name])

            if item.name in custom_construct_txt:
                construct_txt = custom_construct_txt[item.name]

            construct_txt = copy_pnext + copy_strings + construct_txt

            if item.name in custom_destruct_txt:
                destruct_txt = custom_destruct_txt[item.name]

            if copy_pnext:
                destruct_txt += '    if (pNext)\n'
                destruct_txt += '        FreePnextChain(pNext);\n'

            if (self.structOrUnion[item.name] == 'union'):
                if (item.name == 'VkDescriptorDataEXT'):
                    default_init_list = ' type_at_end {0},'
                    safe_struct_body.append("\n%s::%s(const %s* in_struct%s, [[maybe_unused]] PNextCopyState* copy_state)\n{\n%s}" % (ss_name, ss_name, item.name, self.custom_construct_params.get(item.name, ''), construct_txt))
                else:
                    # Unions don't allow multiple members in the initialization list, so just call initialize
                    safe_struct_body.append("\n%s::%s(const %s* in_struct%s, PNextCopyState*)\n{\n    initialize(in_struct);\n}" % (ss_name, ss_name, item.name, self.custom_construct_params.get(item.name, '')))
            else:
                safe_struct_body.append("\n%s::%s(const %s* in_struct%s, [[maybe_unused]] PNextCopyState* copy_state) :%s\n{\n%s}" % (ss_name, ss_name, item.name, self.custom_construct_params.get(item.name, ''), init_list, construct_txt))
            if '' != default_init_list:
                default_init_list = " :%s" % (default_init_list[:-1])
            default_init_body = '\n' + custom_defeault_construct_txt[item.name] if item.name in custom_defeault_construct_txt else ''
            safe_struct_body.append("\n%s::%s()%s\n{%s}" % (ss_name, ss_name, default_init_list, default_init_body))
            # Create slight variation of init and construct txt for copy constructor that takes a copy_src object reference vs. struct ptr
            copy_construct_init = init_func_txt.replace('in_struct->', 'copy_src.')
            copy_construct_init = copy_construct_init.replace(', copy_state', '')
            if item.name == 'VkDescriptorGetInfoEXT':
                copy_construct_init = copy_construct_init.replace(', copy_src.type', '')
            copy_construct_txt = re.sub('(new \\w+)\\(in_struct->', '\\1(*copy_src.', construct_txt) # Pass object to copy constructors
            copy_construct_txt = copy_construct_txt.replace('in_struct->', 'copy_src.')              # Modify remaining struct refs for copy_src object
            copy_construct_txt = copy_construct_txt .replace(', copy_state', '')              # Modify remaining struct refs for copy_src object
            if item.name in custom_copy_txt:
                copy_construct_txt = custom_copy_txt[item.name]
            copy_assign_txt = '    if (&copy_src == this) return *this;\n\n' + destruct_txt + '\n' + copy_construct_init + copy_construct_txt + '\n    return *this;'
            safe_struct_body.append("\n%s::%s(const %s& copy_src)\n{\n%s%s}" % (ss_name, ss_name, ss_name, copy_construct_init, copy_construct_txt)) # Copy constructor
            safe_struct_body.append("\n%s& %s::operator=(const %s& copy_src)\n{\n%s\n}" % (ss_name, ss_name, ss_name, copy_assign_txt)) # Copy assignment operator
            safe_struct_body.append("\n%s::~%s()\n{\n%s}" % (ss_name, ss_name, destruct_txt))
            safe_struct_body.append("\nvoid %s::initialize(const %s* in_struct%s, [[maybe_unused]] PNextCopyState* copy_state)\n{\n%s%s%s}" % (ss_name, item.name, self.custom_construct_params.get(item.name, ''),
                                    destruct_txt, init_func_txt, construct_txt))
            # Copy initializer uses same txt as copy constructor but has a ptr and not a reference
            init_copy = copy_construct_init.replace('copy_src.', 'copy_src->')
            init_copy = re.sub(r'&copy_src(?!->)', 'copy_src', init_copy)           # Replace '&copy_src' with 'copy_src' unless it's followed by a dereference
            init_construct = copy_construct_txt.replace('copy_src.', 'copy_src->')
            init_construct = re.sub(r'&copy_src(?!->)', 'copy_src', init_construct) # Replace '&copy_src' with 'copy_src' unless it's followed by a dereference
            safe_struct_body.append("\nvoid %s::initialize(const %s* copy_src, [[maybe_unused]] PNextCopyState* copy_state)\n{\n%s%s}" % (ss_name, ss_name, init_copy, init_construct))
            if item.ifdef_protect is not None:
                safe_struct_body.append("#endif // %s\n" % item.ifdef_protect)
        return "\n".join(safe_struct_body)
    #
    # Create a helper file and return it as a string
    def OutputDestFile(self):
        if self.helper_file_type == 'safe_struct_source':
            return self.GenerateSafeStructHelperSource()
        elif self.helper_file_type == 'extension_helper_header':
            return self.GenerateExtensionHelperHeader()
        else:
            return 'Bad Helper File Generator Option %s' % self.helper_file_type

    # Check if attribute is "true"
    def getBoolAttribute(self, member, name):
        try: return member.attrib[name].lower() == 'true'
        except: return False
