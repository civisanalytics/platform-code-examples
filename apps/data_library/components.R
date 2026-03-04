# Demo App - UI Components
# Derived from apps/mdive_landing_page/components.R
# Changes: removed civis dependency (get_org_admins), inlined 18f_custom_ui.R,
# simplified boxButtonServer to always grant access (no access gate).

# Inlined from style_files/18f_custom_ui.R
actionButton18F <- function(..., theme = 'light') {
  actionButton(..., class = ifelse(theme == 'light', 'btn-18f-light', 'btn-18f-dark'))
}


#' Adds "//" to "(" and ")" characters so str_detect works correctly for filtering
#' @param x a string
add_backslash_to_string = function(x){
  v = paste(x, collapse = '|')
  v = gsub("(", "\\(", v, fixed = TRUE)
  v = gsub(")", "\\)", v, fixed = TRUE)
}


#' Gets unique categories from a ';'-separated column across both reports and data inventories.
get_unique_choices = function(reports_data, report_col, data, data_col){

  report_choices <- unlist(lapply(reports_data[report_col], function(x) strsplit(x, ';'))) %>%
    trimws('both') %>%
    unique()

  catalog_choices <- unlist(lapply(data[data_col], function(x) strsplit(x, ';'))) %>%
    trimws('both') %>%
    unique()

  all_choices <- unique(c(report_choices, catalog_choices))

  return(all_choices)
}


#' Orders a vector so 'Other' appears at the bottom.
sort_other = function(unique_choices){
  if ('Other' %in% unique_choices){
    choices = unique_choices[!unique_choices == 'Other']
    choices = sort(choices)
    choices = c(choices, 'Other')
  } else {
    choices = sort(unique_choices)
  }
  return(choices)
}


create_buttons = function(text_list, filter_list, ns, tag_separator = ';'){

  button_tags <- tagList()

  if (length(text_list) == 0){
    button_tags = "None"
  } else {
    text_list_length <- length(text_list)
    i <- 1
    for (text in text_list) {
      if (i == text_list_length) {
        text_label <- text
      } else {
        text_label <- paste0(text, tag_separator)
      }
      if (text != '') {
        btn_class <- ifelse(text %in% filter_list,
                            'btn-18f-selected',
                            'btn-18f')
        button_text <- ifelse(
          text %in% filter_list,
          'Click to remove from filter',
          'Click to add to filter'
        )
        button_tags <- tagList(button_tags,
                               actionLink(
                                 inputId = ns(str_replace_all(text, "[^A-Za-z]", "")),
                                 label = text_label,
                               ),
                               bsTooltip(ns(str_replace_all(text, "[^A-Za-z]", "")), button_text)
        )
      }
      i <- i + 1
    }
  }

  return(button_tags)
}


update_input = function(input, text_list, filter_list, parent_session, input_id) {
  lapply(
    text_list,
    function(text) {
      observeEvent(input[[str_replace_all(text, "[^A-Za-z,]", "")]], {
        if (text %in% filter_list()) {
          new_list <- filter_list()[!filter_list() == text]
        } else {
          new_list <- c(filter_list(), text)
        }
        updatePickerInput(parent_session, input_id, selected = new_list)
      })
    }
  )
}


resultsCardUI <- function(id, input_data, rownum,
                          tag_filter_list, tech_area_filter_list) {

  ns <- NS(id)

  tag_list <- input_data[rownum, 'tags'] %>% str_split(';') %>% unlist() %>% trimws('both')
  tech_area_list <- input_data[rownum, 'technical_area'] %>% str_split(';') %>% unlist() %>% trimws('both')

  tag_buttons = create_buttons(tag_list, tag_filter_list, ns)
  tech_area_buttons = create_buttons(tech_area_list, tech_area_filter_list, ns)

  wellPanel(style = "background-color:white; color:black",
    bsTooltip(id = ns('link_title'), title = 'Click to view full description',
              placement = "right", trigger = 'hover', options = list(container = "body")),
    div(class = 'row results-header', style = 'padding-left:12px',
        strong(input_data[rownum, "name"])
    ),
    div(class = 'row results-body',
        div(class = 'col-sm-8 results-body-main',
            p(HTML(str_trunc(gsub("\n", "<br/>", input_data[rownum, "description"]),
                             width = 450,
                             ellipsis = "...")))
        ),
        div(class = 'col-sm-4 results-body-side border-left',
            h4("Data Updated on:"),
            p(input_data[rownum, "clean_last_data_update"]),
            h4("Access Restrictions"),
            p(input_data[rownum, "access_restrictions"]))
    ),
    div(class = 'results-details',
        'Technical area:', tech_area_buttons,
        br(),
        'Tags:', tag_buttons
    )
  )
}


resultsCardServer <- function(id, parent_session, data, row,
                              tag_filter_list, tech_area_filter_list) {

  moduleServer(id, function(input, output, session) {
    tag_list <- data[row, 'tags'] %>% str_split(';') %>% unlist() %>% trimws('both')
    tech_area_list <- data[row, 'technical_area'] %>% str_split(';') %>% unlist() %>% trimws('both')

    update_input(input, tag_list, tag_filter_list, parent_session, 'dataset_choice')
    update_input(input, tech_area_list, tech_area_filter_list, parent_session, 'tech_area')
  })
}


boxButtonUI <- function(id, box_link, description, tooltip_text, development_status,
                        tag_list, tag_filter_list = c(),
                        tech_area_list, tech_area_filter_list = c()) {
  ns <- NS(id)

  tag_buttons = create_buttons(tag_list, tag_filter_list, ns)
  tech_area_buttons = create_buttons(tech_area_list, tech_area_filter_list, ns)

  box(
    id = ns('box_info'),
    status = 'primary',
    title = tags$div(
      style = 'display:inline-block',
      uiOutput(ns("box_title")),
      class = 'report-header'
    ),
    div(class = 'results-body-report-main', style = 'border-bottom:1px solid rgb(241, 241, 241)',
        tags$p(HTML('<b> Status: </b>', development_status)),
        tags$p(description)
    ),
    bsTooltip(id = ns('box_title'), title = tooltip_text,
              placement = "right", trigger = 'hover', options = list(container = "body")),
    div(class = 'results-body-report-details',
        div(id = ns("icon_box"), 'Technical Area:', tech_area_buttons),
        div(id = ns("icon_box"), 'Tags:', tag_buttons)
    ),
    width = 12
  )
}


# Simplified: all reports are always accessible in the demo (no access gate)
boxButtonServer <- function(id, link, box_title_text,
                            tag_list = c(), tag_filter_list = NULL,
                            tech_area_list = c(), tech_area_filter_list = NULL,
                            parent_session = NULL) {
  moduleServer(id, function(input, output, session) {

    update_input(input, tag_list, tag_filter_list, parent_session, 'dataset_choice')
    update_input(input, tech_area_list, tech_area_filter_list, parent_session, 'tech_area')

    output$box_title <- renderUI({
      tags$a(
        href = link,
        HTML(paste(tags$u(box_title_text))),
        target = '_blank'
      )
    })
  })
}
