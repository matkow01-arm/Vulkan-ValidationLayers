// *** THIS FILE IS GENERATED - DO NOT EDIT ***
// See format_utils_generator.py for modifications

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
****************************************************************************/

// NOLINTBEGIN
#pragma once
#include <vulkan/vk_layer.h>

#ifdef __cplusplus
extern "C" {
#endif

static constexpr uint32_t FORMAT_MAX_PLANES = 3;
static constexpr uint32_t FORMAT_MAX_COMPONENTS = 4;

enum class FORMAT_NUMERICAL_TYPE {
    NONE = 0,
    SFLOAT,
    SINT,
    SNORM,
    SRGB,
    SSCALED,
    UFLOAT,
    UINT,
    UNORM,
    USCALED
};

enum class FORMAT_COMPATIBILITY_CLASS {
    NONE = 0,
    ASTC_10X10,
    ASTC_10X5,
    ASTC_10X6,
    ASTC_10X8,
    ASTC_12X10,
    ASTC_12X12,
    ASTC_4X4,
    ASTC_5X4,
    ASTC_5X5,
    ASTC_6X5,
    ASTC_6X6,
    ASTC_8X5,
    ASTC_8X6,
    ASTC_8X8,
    BC1_RGB,
    BC1_RGBA,
    BC2,
    BC3,
    BC4,
    BC5,
    BC6H,
    BC7,
    D16,
    D16S8,
    D24,
    D24S8,
    D32,
    D32S8,
    EAC_R,
    EAC_RG,
    ETC2_EAC_RGBA,
    ETC2_RGB,
    ETC2_RGBA,
    PVRTC1_2BPP,
    PVRTC1_4BPP,
    PVRTC2_2BPP,
    PVRTC2_4BPP,
    S8,
    _10BIT_2PLANE_420,
    _10BIT_2PLANE_422,
    _10BIT_2PLANE_444,
    _10BIT_3PLANE_420,
    _10BIT_3PLANE_422,
    _10BIT_3PLANE_444,
    _128BIT,
    _12BIT_2PLANE_420,
    _12BIT_2PLANE_422,
    _12BIT_2PLANE_444,
    _12BIT_3PLANE_420,
    _12BIT_3PLANE_422,
    _12BIT_3PLANE_444,
    _16BIT,
    _16BIT_2PLANE_420,
    _16BIT_2PLANE_422,
    _16BIT_2PLANE_444,
    _16BIT_3PLANE_420,
    _16BIT_3PLANE_422,
    _16BIT_3PLANE_444,
    _192BIT,
    _24BIT,
    _256BIT,
    _32BIT,
    _32BIT_B8G8R8G8,
    _32BIT_G8B8G8R8,
    _48BIT,
    _64BIT,
    _64BIT_B10G10R10G10,
    _64BIT_B12G12R12G12,
    _64BIT_B16G16R16G16,
    _64BIT_G10B10G10R10,
    _64BIT_G12B12G12R12,
    _64BIT_G16B16G16R16,
    _64BIT_R10G10B10A10,
    _64BIT_R12G12B12A12,
    _8BIT,
    _8BIT_2PLANE_420,
    _8BIT_2PLANE_422,
    _8BIT_2PLANE_444,
    _8BIT_3PLANE_420,
    _8BIT_3PLANE_422,
    _8BIT_3PLANE_444,
    _96BIT
};

// Numeric
// Formats with more then one numeric type (VK_FORMAT_D16_UNORM_S8_UINT) will return false
bool FormatIsSFLOAT(VkFormat format);
bool FormatIsSINT(VkFormat format);
bool FormatIsSNORM(VkFormat format);
bool FormatIsSRGB(VkFormat format);
bool FormatIsSSCALED(VkFormat format);
bool FormatIsUFLOAT(VkFormat format);
bool FormatIsUINT(VkFormat format);
bool FormatIsUNORM(VkFormat format);
bool FormatIsUSCALED(VkFormat format);

// Types from "Interpretation of Numeric Format" table (OpTypeFloat vs OpTypeInt)
static inline bool FormatIsSampledInt(VkFormat format) { return (FormatIsSINT(format) || FormatIsUINT(format)); }
static inline bool FormatIsSampledFloat(VkFormat format) {
    return (FormatIsUNORM(format)   || FormatIsSNORM(format)   ||
            FormatIsUSCALED(format) || FormatIsSSCALED(format) ||
            FormatIsUFLOAT(format)  || FormatIsSFLOAT(format)  ||
            FormatIsSRGB(format));
}

// Compressed
bool FormatIsCompressed_ASTC_HDR(VkFormat format);
bool FormatIsCompressed_ASTC_LDR(VkFormat format);
bool FormatIsCompressed_BC(VkFormat format);
bool FormatIsCompressed_EAC(VkFormat format);
bool FormatIsCompressed_ETC2(VkFormat format);
bool FormatIsCompressed_PVRTC(VkFormat format);
bool FormatIsCompressed(VkFormat format);

// Depth/Stencil
bool FormatIsDepthOrStencil(VkFormat format);
bool FormatIsDepthAndStencil(VkFormat format);
bool FormatIsDepthOnly(VkFormat format);
bool FormatIsStencilOnly(VkFormat format);
static inline bool FormatHasDepth(VkFormat format) { return (FormatIsDepthOnly(format) || FormatIsDepthAndStencil(format)); }
static inline bool FormatHasStencil(VkFormat format) { return (FormatIsStencilOnly(format) || FormatIsDepthAndStencil(format)); }
uint32_t FormatDepthSize(VkFormat format);
uint32_t FormatStencilSize(VkFormat format);
FORMAT_NUMERICAL_TYPE FormatDepthNumericalType(VkFormat format);
FORMAT_NUMERICAL_TYPE FormatStencilNumericalType(VkFormat format);

// Packed
bool FormatIsPacked(VkFormat format);

// YCbCr
bool FormatRequiresYcbcrConversion(VkFormat format);
bool FormatIsXChromaSubsampled(VkFormat format);
bool FormatIsYChromaSubsampled(VkFormat format);

// Multiplane
// Single-plane "_422" formats are treated as 2x1 compressed (for copies)

constexpr bool FormatIsSinglePlane_422(VkFormat format) {
    bool found = false;
    switch (format) {
        case VK_FORMAT_G8B8G8R8_422_UNORM:
        case VK_FORMAT_B8G8R8G8_422_UNORM:
        case VK_FORMAT_G10X6B10X6G10X6R10X6_422_UNORM_4PACK16:
        case VK_FORMAT_B10X6G10X6R10X6G10X6_422_UNORM_4PACK16:
        case VK_FORMAT_G12X4B12X4G12X4R12X4_422_UNORM_4PACK16:
        case VK_FORMAT_B12X4G12X4R12X4G12X4_422_UNORM_4PACK16:
        case VK_FORMAT_G16B16G16R16_422_UNORM:
        case VK_FORMAT_B16G16R16G16_422_UNORM:
            found = true;
            break;
        default:
            break;
    }
    return found;
}

// Returns number of planes in format (which is 1 by default)
constexpr uint32_t FormatPlaneCount(VkFormat format) {
    switch (format) {
        case VK_FORMAT_G8_B8R8_2PLANE_420_UNORM:
        case VK_FORMAT_G8_B8R8_2PLANE_422_UNORM:
        case VK_FORMAT_G10X6_B10X6R10X6_2PLANE_420_UNORM_3PACK16:
        case VK_FORMAT_G10X6_B10X6R10X6_2PLANE_422_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4R12X4_2PLANE_420_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4R12X4_2PLANE_422_UNORM_3PACK16:
        case VK_FORMAT_G16_B16R16_2PLANE_420_UNORM:
        case VK_FORMAT_G16_B16R16_2PLANE_422_UNORM:
        case VK_FORMAT_G8_B8R8_2PLANE_444_UNORM:
        case VK_FORMAT_G10X6_B10X6R10X6_2PLANE_444_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4R12X4_2PLANE_444_UNORM_3PACK16:
        case VK_FORMAT_G16_B16R16_2PLANE_444_UNORM:
            return 2;
        case VK_FORMAT_G8_B8_R8_3PLANE_420_UNORM:
        case VK_FORMAT_G8_B8_R8_3PLANE_422_UNORM:
        case VK_FORMAT_G8_B8_R8_3PLANE_444_UNORM:
        case VK_FORMAT_G10X6_B10X6_R10X6_3PLANE_420_UNORM_3PACK16:
        case VK_FORMAT_G10X6_B10X6_R10X6_3PLANE_422_UNORM_3PACK16:
        case VK_FORMAT_G10X6_B10X6_R10X6_3PLANE_444_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4_R12X4_3PLANE_420_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4_R12X4_3PLANE_422_UNORM_3PACK16:
        case VK_FORMAT_G12X4_B12X4_R12X4_3PLANE_444_UNORM_3PACK16:
        case VK_FORMAT_G16_B16_R16_3PLANE_420_UNORM:
        case VK_FORMAT_G16_B16_R16_3PLANE_422_UNORM:
        case VK_FORMAT_G16_B16_R16_3PLANE_444_UNORM:
            return 3;
        default:
            return 1;
     }
}

constexpr bool FormatIsMultiplane(VkFormat format) { return ((FormatPlaneCount(format)) > 1u); }
VkFormat FindMultiplaneCompatibleFormat(VkFormat mp_fmt, VkImageAspectFlags plane_aspect);
VkExtent2D FindMultiplaneExtentDivisors(VkFormat mp_fmt, VkImageAspectFlags plane_aspect);

// Size
uint32_t FormatComponentCount(VkFormat format);
VkExtent3D FormatTexelBlockExtent(VkFormat format);
FORMAT_COMPATIBILITY_CLASS FormatCompatibilityClass(VkFormat format);
bool FormatElementIsTexel(VkFormat format);
uint32_t FormatElementSize(VkFormat format, VkImageAspectFlags aspectMask = VK_IMAGE_ASPECT_COLOR_BIT);
double FormatTexelSize(VkFormat format, VkImageAspectFlags aspectMask = VK_IMAGE_ASPECT_COLOR_BIT);
// True if Format contains a 64-bit component

constexpr bool FormatIs64bit(VkFormat format) {
    bool found = false;
    switch (format) {
        case VK_FORMAT_R64_UINT:
        case VK_FORMAT_R64_SINT:
        case VK_FORMAT_R64_SFLOAT:
        case VK_FORMAT_R64G64_UINT:
        case VK_FORMAT_R64G64_SINT:
        case VK_FORMAT_R64G64_SFLOAT:
        case VK_FORMAT_R64G64B64_UINT:
        case VK_FORMAT_R64G64B64_SINT:
        case VK_FORMAT_R64G64B64_SFLOAT:
        case VK_FORMAT_R64G64B64A64_UINT:
        case VK_FORMAT_R64G64B64A64_SINT:
        case VK_FORMAT_R64G64B64A64_SFLOAT:
            found = true;
            break;
        default:
            break;
    }
    return found;
}

// Components
bool FormatHasComponentSize(VkFormat format, uint32_t size);
bool FormatHasRed(VkFormat format);
bool FormatHasGreen(VkFormat format);
bool FormatHasBlue(VkFormat format);
bool FormatHasAlpha(VkFormat format);
bool FormatsSameComponentBits(VkFormat format_a, VkFormat format_b);


// Utils/misc
static inline bool FormatIsUndef(VkFormat format) { return (format == VK_FORMAT_UNDEFINED); }
// "blocked image" are defined in the spec (vkspec.html#blocked-image)
static inline bool FormatIsBlockedImage(VkFormat format) {
    return (FormatIsCompressed(format) || FormatIsSinglePlane_422(format));
}
// No official spec definition of "color format"
// So anything that could NOT be a "color format" is a color format
static inline bool FormatIsColor(VkFormat format) {
    return !(FormatIsUndef(format) || FormatIsDepthOrStencil(format) || FormatIsMultiplane(format));
}

#ifdef __cplusplus
}
#endif
// NOLINTEND
