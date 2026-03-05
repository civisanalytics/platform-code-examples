# M-DIVE Landing Page — Demo Version
# Derived from apps/mdive_landing_page/app.R

install.packages("shinycssloaders")

library(shiny)
library(shinydashboard)
library(stringr)
library(dplyr)
library(shinyBS)
library(shinyWidgets)
library(shinycssloaders)
library(shinyjs)

source('components.R')
source('app-text.R')
source('demo-data.R')

# ── Derived filter choices ────────────────────────────────────────────────────

tag_choices <- get_unique_choices(reports_data, 'tags', data, 'tags')
tag_choices_br <- stringr::str_wrap(tag_choices, width = 35)
tag_choices_br <- stringr::str_replace_all(tag_choices_br, "\n", "<br/>     ")

tech_area_choices <- get_unique_choices(reports_data, 'technical_area', data, 'technical_area')
tech_area_choices_br <- stringr::str_wrap(tech_area_choices, width = 35)
tech_area_choices_br <- stringr::str_replace_all(tech_area_choices_br, "\n", "<br/>     ")

# ── UI ────────────────────────────────────────────────────────────────────────

ui <- function(request) {
  dashboardPage(skin = 'black',

    dashboardHeader(title = "Welcome to the Demo Dashboard", titleWidth = 350),

    dashboardSidebar(
      sidebarMenu(
        id = "tabs",
        div(class = 'sidebar-menu', id = "sidebar_nav",
            menuItem("About",          tabName = "home"),
            menuItem("Demo Reports", tabName = "reports", selected = TRUE),
            menuItem("Demo Data Catalog",   tabName = "overview")
        ),
        div(class = 'sidebar-menu', id = 'sidebar_filters',
            conditionalPanel(
              "input.tabs == 'reports' | input.tabs == 'overview'",
              pickerInput(
                width    = '200px',
                inputId  = "tech_area",
                label    = HTML("Filter by <br> Technical Area"),
                choices  = sort_other(tech_area_choices),
                multiple = TRUE,
                selected = NULL,
                choicesOpt = list(
                  style   = rep_len("color:black;", length(tech_area_choices)),
                  content = sort_other(tech_area_choices_br)
                ),
                options = pickerOptions(
                  actionsBox              = TRUE,
                  liveSearch              = TRUE,
                  dropupAuto              = FALSE,
                  size                    = 8,
                  iconBase                = "",
                  tickIcon                = "fa fa-check",
                  `selected-text-format` = "count",
                  `count-selected-text`  = "{0} of {1} Technical Areas Chosen"
                )
              ),
              pickerInput(
                width    = '200px',
                inputId  = "dataset_choice",
                label    = HTML("Or filter by <br> Tags"),
                choices  = sort_other(tag_choices),
                multiple = TRUE,
                selected = NULL,
                choicesOpt = list(
                  style   = rep_len("color:black;", length(tag_choices)),
                  content = sort_other(tag_choices_br)
                ),
                options = pickerOptions(
                  actionsBox             = TRUE,
                  liveSearch             = TRUE,
                  dropupAuto             = FALSE,
                  size                   = 8,
                  iconBase               = "",
                  tickIcon               = "fa fa-check",
                  `selected-text-format` = "count",
                  `count-selected-text`  = "{0} of {1} Tags Chosen"
                )
              )
            )
        )
      )
    ),

    dashboardBody(
      shinyjs::useShinyjs(),
      tags$script("document.getElementsByClassName('sidebar-toggle')[0].style.visibility = 'hidden';"),
      includeCSS('styles.css'),

      tabItems(

        # ── About Tab ──────────────────────────────────────────────────────
        tabItem(tabName = 'home',
          fluidRow(shinydashboard::box(
            id = 'welcome_flip', status = "info",
            title = span(icon("home", lib = "font-awesome"), ' Welcome'),
            width = 12, closable = FALSE, collapsible = TRUE,
            solidHeader = TRUE, collapsed = FALSE,
            p(HTML(welcome_text))
          )),
          br(),
          fluidRow(shinydashboard::box(
            id = 'report_flip', status = "info",
            title = span(icon("chart-line", lib = "font-awesome"),
                         actionLink('reports_go', ' Demo Reports',
                                    style = 'text-decoration:underline')),
            width = 12, closable = FALSE, collapsible = TRUE,
            solidHeader = TRUE, collapsed = TRUE,
            p(HTML(reports_welcome_text))
          )),
          br(),
          fluidRow(shinydashboard::box(
            id = 'data_flip', status = "info",
            title = span(icon("database", lib = "font-awesome"),
                         actionLink('data_go', ' Demo Data Catalog',
                                    style = 'text-decoration:underline')),
            width = 12, closable = FALSE, collapsible = TRUE,
            solidHeader = TRUE, collapsed = TRUE,
            p(HTML(data_welcome_text))
          )),
          br(),
          fluidRow(shinydashboard::box(
            id = 'help_flip', status = "info",
            title = span(icon("question", lib = "font-awesome"), " Help"),
            width = 12, closable = FALSE, collapsible = TRUE,
            solidHeader = TRUE, collapsed = TRUE,
            p(HTML(help_welcome_text))
          ))
        ),

        # ── Demo Reports Tab ─────────────────────────────────────────────
        tabItem(tabName = 'reports',
          div(id = "demo_reports",
              style = 'overflow-x:hidden;overflow-y:scroll;max-height:600px;width:100%;padding-right:4px',
              fluidRow(
                column(6,
                       textInput("search_box_reports", label = "Search",
                                 placeholder = "Search...", width = '86.5%')),
                column(6,
                       pickerInput(
                         inputId = 'order_results_reports',
                         label   = "Order by",
                         choices = c(
                           'Featured'         = 'featured',
                           'Report Name: A-Z' = 'name',
                           'Category'         = 'category'
                         ),
                         choicesOpt = list(style = rep_len("color:black;", 3))
                       ))
              ),
              uiOutput('reportHeading'),
              uiOutput('reports_page') %>% withSpinner(color = "#2474a4")
          )
        ),

        # ── Data Catalog Tab ───────────────────────────────────────────────
        tabItem(tabName = 'overview',
          fluidPage(
            fluidRow(
              column(6,
                     textInput("search_box", label = "Search",
                               placeholder = "Search...", width = '86.5%')),
              column(6,
                     selectInput('order_results', "Order by",
                                 choices = c(
                                   'Dataset Name: A-Z'            = 'name',
                                   'Last Updated: Oldest to Newest' = 'last_data_update'
                                 )))
            )
          ),
          fluidPage(
            div(style = 'overflow-x:hidden;overflow-y:scroll;max-height:600px;width:100%;padding-right:4px',
                id = "data_catalog",
                uiOutput('cardHeading'),
                uiOutput('cardContents') %>% withSpinner(color = "#2474a4"))
          )
        )

      ) # end tabItems
    ) # end dashboardBody
  )
}

# ── Server ────────────────────────────────────────────────────────────────────

server <- function(input, output, session) {

  # ── Dataset selection (for modal) ─────────────────────────────────────────
  selection <- reactiveValues(name = NULL)

  # ── Filtered Data Reactives ───────────────────────────────────────────────

  filtered_data <- reactive({
    tag_selections      <- add_backslash_to_string(input$dataset_choice)
    tech_area_selections <- add_backslash_to_string(input$tech_area)

    output <- data

    if (!is.null(input$dataset_choice)) {
      output <- output %>% dplyr::filter(str_detect(tags, tag_selections))
    }

    if (!is.null(input$tech_area)) {
      output <- output %>% dplyr::filter(str_detect(technical_area, tech_area_selections))
    }

    if (!is.na(input$search_box) & input$search_box != "") {
      output <- output %>%
        filter_all(any_vars(agrepl(input$search_box, ., ignore.case = TRUE)))
    }

    if (!is.null(input$order_results)) {
      output <- output %>% arrange_at(.vars = c(input$order_results, 'name'))
    }

    output
  })

  filtered_reports <- reactive({
    tag_selections       <- add_backslash_to_string(input$dataset_choice)
    tech_area_selections <- add_backslash_to_string(input$tech_area)

    output <- reports_data

    if (!is.null(input$dataset_choice)) {
      output <- output %>% dplyr::filter(str_detect(tags, tag_selections))
    }

    if (!is.null(input$tech_area)) {
      output <- output %>% dplyr::filter(str_detect(technical_area, tech_area_selections))
    }

    if (!is.na(input$search_box_reports) & input$search_box_reports != "") {
      output <- output %>%
        filter_all(any_vars(agrepl(input$search_box_reports, ., ignore.case = TRUE)))
    }

    if (!is.null(input$order_results_reports)) {
      output <- output %>% arrange_at(.vars = c(input$order_results_reports, 'name'))
    }

    output
  })

  # ── Reports Tab ───────────────────────────────────────────────────────────

  output$reports_page <- renderUI({
    if (nrow(filtered_reports()) >= 1) {

      results <- lapply(1:nrow(filtered_reports()), function(rownum) {
        boxButtonUI(
          id = str_replace_all(
            filtered_reports()[rownum, 'name'],
            c(':' = '', ',' = '', '-' = '', ' ' = '_', '\\(' = '', '\\)' = '', '&' = '')
          ),
          box_link           = filtered_reports()[rownum, 'location_link'],
          development_status = filtered_reports()[rownum, 'development_status'],
          description        = filtered_reports()[rownum, 'description'],
          tooltip_text       = "Click to open this report in a new tab",
          tag_list           = strsplit(filtered_reports()[rownum, 'tags'], ';') %>% unlist() %>% trimws('both'),
          tag_filter_list    = input$dataset_choice,
          tech_area_list     = strsplit(filtered_reports()[rownum, 'technical_area'], ';') %>% unlist() %>% trimws('both'),
          tech_area_filter_list = input$tech_area
        )
      })

      # Insert category/featured headers when sorting by category or featured
      if (input$order_results_reports %in% c('category')) {
        category_counts <- filtered_reports() %>%
          dplyr::mutate(position = row_number()) %>%
          dplyr::group_by(!!dplyr::sym(input$order_results_reports)) %>%
          dplyr::mutate(group_start_position = row_number()) %>%
          dplyr::filter(group_start_position == 1) %>%
          dplyr::select(!!sym(input$order_results_reports), position)

        for (i in 1:nrow(category_counts)) {
          insert_position <- category_counts$position[i] + i - 1
          html_headers    <- strong(h3(category_counts[[input$order_results_reports]][[i]]))
          results         <- append(results, list(html_headers), insert_position - 1)
        }
      }

    } else {
      results <- fluidRow(width = 12,
                          actionLink("reset_input", "Reset your filters to view more results.",
                                     style = "margin-left: 15px"))
    }
    results
  })

  dataset_choices        <- reactive(input$dataset_choice)
  tech_area_input_choices <- reactive(input$tech_area)

  lapply(1:nrow(reports_data), function(rownum) {
    boxButtonServer(
      id = str_replace_all(
        reports_data[rownum, 'name'],
        c(':' = '', ',' = '', '-' = '', ' ' = '_', '\\(' = '', '\\)' = '', '&' = '')
      ),
      link           = reports_data[rownum, 'location_link'],
      box_title_text = h3(span(reports_data[rownum, 'name'],
                               icon("external-link-alt", lib = "font-awesome"))),
      tag_list           = strsplit(reports_data[rownum, 'tags'], ';') %>% unlist() %>% trimws('both'),
      tag_filter_list    = dataset_choices,
      tech_area_list     = strsplit(reports_data[rownum, 'technical_area'], ';') %>% unlist() %>% trimws('both'),
      tech_area_filter_list = tech_area_input_choices,
      parent_session     = session
    )
  })

  # ── Data Catalog Tab ──────────────────────────────────────────────────────

  output$cardContents <- renderUI({
    if (nrow(filtered_data()) >= 1) {
      lapply(1:nrow(filtered_data()), function(rownum) {
        resultsCardUI(
          str_replace_all(
            filtered_data()[rownum, 'name'],
            c(':' = '', ',' = '', '-' = '', ' ' = '_', '\\(' = '', '\\)' = '', '&' = '')
          ),
          filtered_data(), rownum,
          tag_filter_list      = input$dataset_choice,
          tech_area_filter_list = input$tech_area
        )
      })
    } else {
      fluidRow(width = 12,
               actionLink("reset_input", "Reset your filters to view more results.",
                          style = "margin-left: 15px"))
    }
  })

  lapply(1:nrow(data), function(rownum) {
    resultsCardServer(
      str_replace_all(
        data[rownum, 'name'],
        c(':' = '', ',' = '', '-' = '', ' ' = '_', '\\(' = '', '\\)' = '', '&' = '')
      ),
      parent_session        = session,
      data                  = data,
      row                   = rownum,
      tag_filter_list       = dataset_choices,
      tech_area_filter_list = tech_area_input_choices,
      selection             = selection
    )
  })

  # ── Dataset detail modal ──────────────────────────────────────────────────

  observeEvent(selection$name, {
    req(selection$name)
    row <- data[data$name == selection$name, ]

    assoc <- row$associated_reports
    assoc_ui <- if (!is.na(assoc) && nchar(trimws(assoc)) > 0) {
      report_names <- trimws(strsplit(assoc, ";")[[1]])
      tags$ul(lapply(report_names, function(r) tags$li(r)))
    } else {
      p("None")
    }

    showModal(modalDialog(
      title = row$name,
      size  = "l",
      easyClose = TRUE,
      footer = modalButton("Close"),
      h4("Description"),
      p(row$full_description),
      tags$hr(),
      fluidRow(
        column(6,
          h4("Technical Area"),  p(row$technical_area),
          h4("Last Updated"),    p(row$clean_last_data_update),
          h4("Access"),          p(row$access_restrictions)
        ),
        column(6,
          h4("Source"),             p(row$source),
          h4("Unit of Analysis"),   p(row$unit_of_analysis),
          h4("Associated Reports"), assoc_ui
        )
      )
    ))
  })

  # ── Headings ──────────────────────────────────────────────────────────────

  output$cardHeading <- renderUI({
    tech_picks <- paste(input$tech_area, collapse = ', ')
    tag_picks  <- paste(input$dataset_choice, collapse = ', ')

    if (nrow(filtered_data()) == 0) {
      out <- "Sorry! No datasets match selected filters."
    } else {
      out <- paste0("Showing ", nrow(filtered_data()), " dataset(s)")
    }

    if (tech_picks != "" & tag_picks == "" & nrow(filtered_data()) > 0)
      out <- HTML(out, " tagged with <b>", tech_picks, "</b> technical area(s)")
    if (tech_picks == "" & tag_picks != "" & nrow(filtered_data()) > 0)
      out <- HTML(out, " tagged with <b>", tag_picks, "</b>.")
    if (tag_picks != "" & tech_picks != "" & nrow(filtered_data()) > 0)
      out <- HTML(out, " tagged with <b>", tag_picks, "</b> AND <b>", tech_picks, "</b> technical area(s)")

    out
  })

  output$reportHeading <- renderUI({
    tech_picks <- paste(input$tech_area, collapse = ', ')
    tag_picks  <- paste(input$dataset_choice, collapse = ', ')

    if (nrow(filtered_reports()) == 0) {
      out <- "Sorry! No reports match selected filters."
    } else {
      out <- paste0("Showing ", nrow(filtered_reports()), " report(s)")
    }

    if (tech_picks != "" & tag_picks == "" & nrow(filtered_reports()) > 0)
      out <- HTML(out, " tagged with <b>", tech_picks, "</b> technical area(s)")
    if (tech_picks == "" & tag_picks != "" & nrow(filtered_reports()) > 0)
      out <- HTML(out, " tagged with <b>", tag_picks, "</b>.")
    if (tag_picks != "" & tech_picks != "" & nrow(filtered_reports()) > 0)
      out <- HTML(out, " tagged with <b>", tag_picks, "</b> AND <b>", tech_picks, "</b> technical area(s)")

    out
  })

  # ── Navigation observers ──────────────────────────────────────────────────

  observeEvent(input$reset_input, {
    updatePickerInput(session, "dataset_choice", selected = "")
    updatePickerInput(session, "tech_area",      selected = "")
    updateTextInput(session,   "search_box",     value   = "")
    updateTextInput(session,   "search_box_reports", value = "")
  })

  observeEvent(input$reports_go, {
    updateTabItems(session, "tabs", "reports")
  })

  observeEvent(input$data_go, {
    updateTabItems(session, "tabs", "overview")
  })

  # Tab bookmarking
  observeEvent(reactiveValuesToList(input), session$doBookmark())
  onBookmarked(updateQueryString)
  observe({
    setBookmarkExclude(dplyr::setdiff(names(input), "tabs"))
  })
}

#### App ####
shinyApp(ui, server, enableBookmarking = "url")
